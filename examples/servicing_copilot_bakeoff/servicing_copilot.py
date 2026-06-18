from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from sqlite3 import Connection
from typing import Any, Iterable


@dataclass(frozen=True)
class EmailClassification:
    intent: str
    priority: str
    next_action: str
    requires_human_review: bool
    confidence: float
    structured_output: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def initialize_database(conn: Connection) -> None:
    conn.executescript(
        """
        create table if not exists lenders (
            id text primary key,
            name text not null,
            created_at text not null default current_timestamp
        );

        create table if not exists loans (
            lender_id text not null,
            loan_number text not null,
            borrower_name text not null,
            principal_balance text not null,
            renewal_date text not null,
            status text not null,
            updated_at text not null default current_timestamp,
            primary key (lender_id, loan_number)
        );

        create table if not exists servicing_cases (
            id integer primary key autoincrement,
            lender_id text not null,
            loan_number text not null,
            case_type text not null,
            status text not null,
            opened_at text not null default current_timestamp,
            unique (lender_id, loan_number, case_type)
        );

        create table if not exists case_events (
            id integer primary key autoincrement,
            lender_id text not null,
            loan_number text not null,
            event_type text not null,
            payload_json text not null,
            created_at text not null default current_timestamp
        );
        """
    )
    conn.commit()


def import_loan_tape(
    conn: Connection, lender_id: str, rows: Iterable[dict[str, Any]]
) -> dict[str, int]:
    stats = {"inserted": 0, "updated": 0, "unchanged": 0}
    conn.execute(
        "insert or ignore into lenders (id, name) values (?, ?)",
        (lender_id, lender_id),
    )

    for raw_row in rows:
        row = _normalize_loan_row(raw_row)
        existing = conn.execute(
            """
            select borrower_name, principal_balance, renewal_date, status
            from loans
            where lender_id = ? and loan_number = ?
            """,
            (lender_id, row["loan_number"]),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                insert into loans (
                    lender_id, loan_number, borrower_name, principal_balance,
                    renewal_date, status
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    lender_id,
                    row["loan_number"],
                    row["borrower_name"],
                    row["principal_balance"],
                    row["renewal_date"],
                    row["status"],
                ),
            )
            _ensure_servicing_case(conn, lender_id, row["loan_number"], row["status"])
            _append_event(conn, lender_id, row["loan_number"], "loan.imported", row)
            stats["inserted"] += 1
            continue

        changed_fields = [
            field
            for field in ("borrower_name", "principal_balance", "renewal_date", "status")
            if existing[field] != row[field]
        ]
        if not changed_fields:
            stats["unchanged"] += 1
            continue

        conn.execute(
            """
            update loans
            set borrower_name = ?, principal_balance = ?, renewal_date = ?,
                status = ?, updated_at = current_timestamp
            where lender_id = ? and loan_number = ?
            """,
            (
                row["borrower_name"],
                row["principal_balance"],
                row["renewal_date"],
                row["status"],
                lender_id,
                row["loan_number"],
            ),
        )
        _ensure_servicing_case(conn, lender_id, row["loan_number"], row["status"])
        _append_event(
            conn,
            lender_id,
            row["loan_number"],
            "loan.updated",
            {"changed_fields": changed_fields, "row": row},
        )
        stats["updated"] += 1

    conn.commit()
    return stats


def classify_borrower_email(email_text: str) -> EmailClassification:
    text = email_text.strip()
    lowered = text.lower()
    promise_date_text = _find_promise_date_text(text)

    if promise_date_text and any(
        phrase in lowered
        for phrase in ("pay", "payment", "bounced", "missed", "nsf")
    ):
        return EmailClassification(
            intent="payment_promise",
            priority="high",
            next_action="record_promise_to_pay",
            requires_human_review=True,
            confidence=0.82,
            structured_output={
                "promise_date_text": promise_date_text,
                "borrower_commitment": text,
                "needs_payment_method_update": "banking" in lowered
                or "account" in lowered,
            },
        )

    if any(phrase in lowered for phrase in ("renew", "renewal", "same rate", "maturity")):
        return EmailClassification(
            intent="renewal_question",
            priority="medium",
            next_action="route_to_renewal_queue",
            requires_human_review=True,
            confidence=0.78,
            structured_output={
                "borrower_question": text,
                "requested_topic": "renewal_terms",
            },
        )

    if any(phrase in lowered for phrase in ("nsf", "bounced", "failed payment")):
        return EmailClassification(
            intent="nsf_follow_up",
            priority="high",
            next_action="request_payment_update",
            requires_human_review=True,
            confidence=0.74,
            structured_output={
                "borrower_message": text,
                "requires_collections_review": True,
            },
        )

    return EmailClassification(
        intent="general_servicing_reply",
        priority="normal",
        next_action="route_to_servicing_inbox",
        requires_human_review=True,
        confidence=0.61,
        structured_output={"borrower_message": text},
    )


def record_email_classification(
    conn: Connection,
    lender_id: str,
    loan_number: str,
    inbound_email_id: str,
    classification: EmailClassification,
) -> None:
    _append_event(
        conn,
        lender_id,
        loan_number,
        "borrower_email.classified",
        {
            "inbound_email_id": inbound_email_id,
            "classification": classification.to_dict(),
        },
    )
    conn.commit()


def _normalize_loan_row(raw_row: dict[str, Any]) -> dict[str, str]:
    required = ("loan_number", "borrower_name", "principal_balance", "renewal_date")
    missing = [field for field in required if not str(raw_row.get(field, "")).strip()]
    if missing:
        raise ValueError(f"missing required loan tape fields: {', '.join(missing)}")

    try:
        principal_balance = Decimal(str(raw_row["principal_balance"])).quantize(
            Decimal("0.01")
        )
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("principal_balance must be a decimal amount") from exc

    return {
        "loan_number": str(raw_row["loan_number"]).strip(),
        "borrower_name": str(raw_row["borrower_name"]).strip(),
        "principal_balance": str(principal_balance),
        "renewal_date": str(raw_row["renewal_date"]).strip(),
        "status": str(raw_row.get("status", "current")).strip() or "current",
    }


def _ensure_servicing_case(
    conn: Connection, lender_id: str, loan_number: str, status: str
) -> None:
    case_type = "renewal" if status == "current" else status
    conn.execute(
        """
        insert or ignore into servicing_cases (
            lender_id, loan_number, case_type, status
        )
        values (?, ?, ?, ?)
        """,
        (lender_id, loan_number, case_type, "open"),
    )


def _append_event(
    conn: Connection,
    lender_id: str,
    loan_number: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        insert into case_events (
            lender_id, loan_number, event_type, payload_json
        )
        values (?, ?, ?, ?)
        """,
        (
            lender_id,
            loan_number,
            event_type,
            json.dumps(payload, sort_keys=True),
        ),
    )


def _find_promise_date_text(text: str) -> str | None:
    match = re.search(
        r"\b(this\s+friday|friday|tomorrow|today|next\s+week)\b",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None
