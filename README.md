# YALA AI Ops P0 Prototype

This is a compact prototype for the Eleduck YALA AI Business Operating System role.

It demonstrates the P0 chain described in the job post:

1. Receive an internal business question from Lark Bot.
2. Retrieve relevant case knowledge from RAGFlow.
3. Ask Dify to produce an AI draft with traceable citations.
4. Write the request, retrieval ids, AI draft, and human-review status into Lark Base.
5. Return a concise Lark message card for review.

The code is intentionally small. It is meant to show integration shape, error handling, and data boundaries before touching a real production tenant.

## Why This Fits P0

The job post is not asking for a generic chatbot. The business needs a loop:

```
business case / client question
  -> retrieve internal examples and rules
  -> generate draft judgment
  -> human correction
  -> save reusable knowledge and audit log
```

This prototype keeps that loop explicit and leaves the data model visible.

## Local Run

```powershell
cd E:\money\earn10000\yala-p0-prototype
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn src.adapter:app --reload --port 8787
```

With mock mode enabled, no external accounts are required:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8787/lark/events `
  -ContentType "application/json" `
  -Body '{"event":{"message":{"chat_id":"demo-chat","content":"客户预算低但要求中东达人直播，是否值得跟进？"}}}'
```

## Production Integration Points

- `LARK_APP_ID`, `LARK_APP_SECRET`: Lark app credentials.
- `LARK_BASE_APP_TOKEN`, `LARK_BASE_TABLE_ID`: AI call log table.
- `DIFY_API_KEY`, `DIFY_WORKFLOW_URL`: Dify workflow endpoint.
- `RAGFLOW_API_KEY`, `RAGFLOW_RETRIEVAL_URL`: RAGFlow retrieval endpoint.

## n8n Workflow Template

An importable n8n workflow skeleton is included at:

```text
n8n/yala-p0-workflow.json
```

It mirrors the FastAPI adapter as a visual workflow:

`webhook -> normalize -> RAGFlow retrieval -> Dify draft -> Lark Base call log -> review response`

See `docs/n8n-workflow.md` for the import notes, required credentials, and production hardening checklist.

## Suggested P0 Acceptance

- A Lark Bot can receive a test message.
- The adapter retrieves 3-5 relevant internal cases or rules from RAGFlow.
- Dify returns an answer with citation references.
- Lark Base receives one log row per call.
- The response card shows draft answer, cited source ids, and review status.
- Secrets are not committed; deployment uses environment variables.
