# Voice AI Vapi Calendar CRM Workflow

File: `n8n/voice-ai-vapi-calendar-crm-workflow.json`

This importable n8n workflow is a portfolio-ready skeleton for Voice AI agency builds. It is designed for Vapi-style custom tools and end-of-call events.

## What it demonstrates

1. Receive a Vapi custom tool call.
2. Normalize the tool request and enforce an allowlist.
3. Forward the tool call to a calendar/CRM gateway.
4. Return the tool result in a Vapi-compatible shape.
5. Receive an end-of-call event.
6. Summarize the transcript with an LLM endpoint.
7. Upsert a call log into a CRM or database.

## Tool-call branch

`Webhook - Vapi Tool Call -> Normalize Tool Call -> Call Calendar or CRM Tool -> Format Vapi Tool Response -> Respond - Tool Result`

Supported tool names in the template:

- `check_availability`
- `create_booking`
- `upsert_contact`
- `cancel_booking`
- `transfer_call`

The allowlist is deliberate. A voice agent should not be able to call arbitrary backend paths.

## End-of-call branch

`Webhook - Vapi Call Ended -> Normalize Call End -> Summarize Call - LLM -> Prepare CRM Call Log -> Upsert CRM Call Log -> Respond - Call Logged`

This branch turns each completed call into a reviewable operational record: transcript, recording URL, summary, lead status, next action, and fields to update.

## Required environment variables

- `VOICE_TOOL_BASE_URL`: internal FastAPI or serverless tool gateway.
- `VOICE_SUMMARY_URL`: LLM summarizer endpoint.
- `VOICE_CRM_LOG_URL`: CRM/database upsert endpoint.

## Required credentials

Use separate HTTP Header Auth credentials for:

- internal tool gateway;
- LLM summarizer;
- CRM/database API.

## Example Vapi tool-call payload

```json
{
  "message": {
    "call": {
      "id": "call_demo_001",
      "customer": {
        "number": "+15555550100"
      }
    },
    "toolCall": {
      "id": "tool_demo_001",
      "function": {
        "name": "check_availability",
        "arguments": "{\"date\":\"2026-06-20\",\"timezone\":\"America/New_York\"}"
      }
    }
  }
}
```

## Example call-ended payload

```json
{
  "message": {
    "call": {
      "id": "call_demo_001",
      "assistantId": "assistant_demo_001",
      "customer": {
        "number": "+15555550100"
      }
    },
    "transcript": "Caller asked for a consultation next week and prefers mornings.",
    "recordingUrl": "https://example.com/recordings/call_demo_001.mp3",
    "endedReason": "customer-ended-call"
  }
}
```

## Production hardening checklist

- Verify Vapi webhook signatures before trusting payloads.
- Store raw payloads for debugging, but redact PII in shared logs.
- Add retry/backoff and dead-letter handling around every HTTP request.
- Make calendar writes idempotent with external call IDs.
- Separate tenant/client credentials so one client cannot affect another.
- Add human approval for destructive actions such as cancellation or escalation.
- Add monitoring for tool-call latency, because voice interactions have tight time budgets.

## Suggested paid pilot scope

Build one working Voice AI backend slice:

- Vapi custom tool endpoint for `check_availability` and `create_booking`;
- one calendar or CRM integration;
- call transcript summary;
- CRM call log;
- error and retry behavior;
- short handoff doc.

Suggested pilot price: USD 500-1200 depending on integrations and credential complexity.
