# n8n Workflow Template

File: `n8n/yala-p0-workflow.json`

This importable n8n workflow mirrors the FastAPI P0 adapter:

1. Receive an internal question through a webhook.
2. Normalize the payload into a small business event.
3. Retrieve relevant cases from RAGFlow.
4. Send the question and retrieved cases to a Dify workflow.
5. Prepare a review record with answer, citations, next action, and status.
6. Write the call log into Lark Base.
7. Return a JSON response for the calling bot or system.

## Why this is useful

Many AI automation projects fail because they are just a prompt connected to an API. This template keeps the operational controls visible:

- input normalization;
- source retrieval;
- structured draft generation;
- call log persistence;
- human-review status;
- explicit next action.

## Required environment variables

- `RAGFLOW_RETRIEVAL_URL`
- `DIFY_WORKFLOW_URL`
- `LARK_BASE_APP_TOKEN`
- `LARK_BASE_TABLE_ID`

## Required n8n credentials

Use separate HTTP Header Auth credentials for:

- RAGFlow API token;
- Dify API token;
- Lark/Feishu tenant access token.

In production, the Lark tenant access token should be refreshed by a separate credential/token workflow rather than pasted manually.

## Test payload

```json
{
  "question": "A low-budget GCC creator campaign asks for live commerce and influencer content. Should sales continue?",
  "requester": "lark-bot",
  "scenario": "lead_qualification"
}
```

## Production hardening

Before using this against real customer data:

- add retry and dead-letter branches around every HTTP request;
- add payload size limits and PII redaction;
- store run IDs and source document IDs;
- split `approved`, `revised`, and `rejected` human-review paths;
- add role-based access control on the Lark Base table.

