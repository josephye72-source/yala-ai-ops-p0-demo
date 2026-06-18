import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="YALA AI Ops P0 Adapter")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


MOCK_MODE = env("MOCK_MODE", "true").lower() == "true"
TIMEOUT = float(env("REQUEST_TIMEOUT_SECONDS", "20"))


class LarkMessage(BaseModel):
    chat_id: str
    content: str


class RetrievedCase(BaseModel):
    source_id: str
    title: str
    snippet: str
    score: float


class DraftAnswer(BaseModel):
    answer: str
    citations: list[str]
    next_action: str


class CallLog(BaseModel):
    question: str
    retrieved: list[RetrievedCase]
    draft: DraftAnswer
    review_status: str = "pending_human_review"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mock_mode": str(MOCK_MODE).lower()}


@app.post("/lark/events")
async def lark_events(payload: dict[str, Any]) -> dict[str, Any]:
    message = parse_lark_message(payload)
    if not message.content:
        raise HTTPException(status_code=400, detail="Empty message content")

    retrieved = await retrieve_cases(message.content)
    draft = await generate_draft(message.content, retrieved)
    log = CallLog(question=message.content, retrieved=retrieved, draft=draft)
    log_id = await write_lark_base_log(log)
    card = build_lark_card(log, log_id)

    if not MOCK_MODE:
        await send_lark_card(message.chat_id, card)

    return {"ok": True, "log_id": log_id, "card": card}


def parse_lark_message(payload: dict[str, Any]) -> LarkMessage:
    event = payload.get("event", {})
    message = event.get("message", {})
    chat_id = message.get("chat_id", "demo-chat")
    content = message.get("content", "")

    if isinstance(content, dict):
        content = content.get("text", "")

    return LarkMessage(chat_id=chat_id, content=str(content).strip())


async def retrieve_cases(question: str) -> list[RetrievedCase]:
    if MOCK_MODE:
        return [
            RetrievedCase(
                source_id="case-2026-001",
                title="Low-budget GCC influencer lead",
                snippet="Low budget plus unclear deliverables usually requires a paid diagnostic call before proposal.",
                score=0.91,
            ),
            RetrievedCase(
                source_id="rule-pricing-003",
                title="Do not reduce core execution scope without changing deliverables",
                snippet="Discounts must map to fewer deliverables, lower reporting depth, or smaller creator pool.",
                score=0.87,
            ),
        ]

    url = env("RAGFLOW_RETRIEVAL_URL")
    key = env("RAGFLOW_API_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Missing RAGFlow configuration")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={"query": question, "top_k": 5},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        RetrievedCase(
            source_id=str(item.get("id", "")),
            title=str(item.get("title", "")),
            snippet=str(item.get("content", ""))[:500],
            score=float(item.get("score", 0)),
        )
        for item in data.get("results", [])
    ]


async def generate_draft(question: str, retrieved: list[RetrievedCase]) -> DraftAnswer:
    if MOCK_MODE:
        return DraftAnswer(
            answer=(
                "建议先进入轻量诊断，不直接承诺完整达人执行。"
                "理由是客户预算低且目标复杂，应先确认目标市场、达人层级、交付口径和回款风险。"
            ),
            citations=[item.source_id for item in retrieved],
            next_action="让业务负责人确认是否收取诊断费，并补充客户预算、目标国家和交付周期。",
        )

    url = env("DIFY_WORKFLOW_URL")
    key = env("DIFY_API_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Missing Dify configuration")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "inputs": {
                    "question": question,
                    "retrieved_cases": [item.model_dump() for item in retrieved],
                },
                "response_mode": "blocking",
                "user": "lark-bot",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    output = data.get("data", {}).get("outputs", {})
    return DraftAnswer(
        answer=str(output.get("answer", "")),
        citations=list(output.get("citations", [])),
        next_action=str(output.get("next_action", "")),
    )


async def write_lark_base_log(log: CallLog) -> str:
    if MOCK_MODE:
        return "mock-log-row-001"

    app_token = env("LARK_BASE_APP_TOKEN")
    table_id = env("LARK_BASE_TABLE_ID")
    if not app_token or not table_id:
        raise HTTPException(status_code=500, detail="Missing Lark Base configuration")

    token = await get_lark_tenant_token()
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    fields = {
        "Question": log.question,
        "Draft Answer": log.draft.answer,
        "Citations": ", ".join(log.draft.citations),
        "Next Action": log.draft.next_action,
        "Review Status": log.review_status,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"fields": fields},
        )
        resp.raise_for_status()
        data = resp.json()

    return str(data.get("data", {}).get("record", {}).get("record_id", ""))


async def get_lark_tenant_token() -> str:
    app_id = env("LARK_APP_ID")
    app_secret = env("LARK_APP_SECRET")
    if not app_id or not app_secret:
        raise HTTPException(status_code=500, detail="Missing Lark credentials")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        resp.raise_for_status()
        data = resp.json()

    token = data.get("tenant_access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Lark did not return a tenant token")
    return str(token)


def build_lark_card(log: CallLog, log_id: str) -> dict[str, Any]:
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "AI 判断草稿待确认"}},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**问题**\n{log.question}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**草稿**\n{log.draft.answer}"}},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**引用来源**\n{', '.join(log.draft.citations)}",
                },
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**下一步**\n{log.draft.next_action}"},
            },
            {"tag": "hr"},
            {"tag": "note", "elements": [{"tag": "plain_text", "content": f"Log: {log_id}"}]},
        ],
    }


async def send_lark_card(chat_id: str, card: dict[str, Any]) -> None:
    token = await get_lark_tenant_token()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": card,
            },
        )
        resp.raise_for_status()

