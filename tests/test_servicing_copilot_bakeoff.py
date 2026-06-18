import json
import sqlite3
import unittest

from examples.servicing_copilot_bakeoff.servicing_copilot import (
    classify_borrower_email,
    initialize_database,
    import_loan_tape,
    record_email_classification,
)


class ServicingCopilotBakeoffTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        initialize_database(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_import_loan_tape_is_idempotent_and_keeps_append_only_events(self):
        row = {
            "loan_number": "L-1001",
            "borrower_name": "Avery Chen",
            "principal_balance": "412500.00",
            "renewal_date": "2026-09-01",
            "status": "current",
        }

        first = import_loan_tape(self.conn, lender_id="lender-demo", rows=[row])
        second = import_loan_tape(self.conn, lender_id="lender-demo", rows=[row])

        loan_count = self.conn.execute("select count(*) from loans").fetchone()[0]
        event_count = self.conn.execute("select count(*) from case_events").fetchone()[0]

        self.assertEqual(first, {"inserted": 1, "updated": 0, "unchanged": 0})
        self.assertEqual(second, {"inserted": 0, "updated": 0, "unchanged": 1})
        self.assertEqual(loan_count, 1)
        self.assertEqual(event_count, 1)

        changed_row = dict(row)
        changed_row["principal_balance"] = "410000.00"

        third = import_loan_tape(self.conn, lender_id="lender-demo", rows=[changed_row])
        events = self.conn.execute(
            "select event_type, payload_json from case_events order by id"
        ).fetchall()

        self.assertEqual(third, {"inserted": 0, "updated": 1, "unchanged": 0})
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_type"], "loan.imported")
        self.assertEqual(events[1]["event_type"], "loan.updated")
        self.assertEqual(
            json.loads(events[1]["payload_json"])["changed_fields"],
            ["principal_balance"],
        )

    def test_classifier_returns_structured_output_for_payment_promise(self):
        classification = classify_borrower_email(
            "Sorry the payment bounced. I can pay the missed payment this Friday "
            "and update my banking info."
        )

        self.assertEqual(classification.intent, "payment_promise")
        self.assertEqual(classification.priority, "high")
        self.assertEqual(classification.next_action, "record_promise_to_pay")
        self.assertTrue(classification.requires_human_review)
        self.assertGreaterEqual(classification.confidence, 0.7)
        self.assertEqual(
            classification.structured_output["promise_date_text"],
            "this Friday",
        )

    def test_recording_classification_appends_audit_event(self):
        import_loan_tape(
            self.conn,
            lender_id="lender-demo",
            rows=[
                {
                    "loan_number": "L-2002",
                    "borrower_name": "Morgan Patel",
                    "principal_balance": "299000.00",
                    "renewal_date": "2026-10-15",
                    "status": "nsf_follow_up",
                }
            ],
        )
        classification = classify_borrower_email(
            "Can you renew my mortgage at the same rate?"
        )

        record_email_classification(
            self.conn,
            lender_id="lender-demo",
            loan_number="L-2002",
            inbound_email_id="email-abc",
            classification=classification,
        )

        event = self.conn.execute(
            "select event_type, payload_json from case_events order by id desc limit 1"
        ).fetchone()
        payload = json.loads(event["payload_json"])

        self.assertEqual(event["event_type"], "borrower_email.classified")
        self.assertEqual(payload["inbound_email_id"], "email-abc")
        self.assertEqual(payload["classification"]["intent"], "renewal_question")
        self.assertTrue(payload["classification"]["requires_human_review"])


if __name__ == "__main__":
    unittest.main()
