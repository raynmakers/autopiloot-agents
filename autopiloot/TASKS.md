# Project Tasks Checklist

Legend: [x] done, [ ] planned

## Core Configuration & Infrastructure

- [ ] 00-config-yaml.mdc — settings.yaml and loader
- [ ] 00-env-config.mdc — environment loader and template
- [ ] 01-scheduling-firebase.mdc — Firebase Functions scheduling and budget trigger
- [ ] 02-idempotency-naming.mdc — idempotency and Drive naming
- [ ] 03-google-sheet-flow.mdc — Sheets ingestion and archival
- [ ] 04-reliability-quotas.mdc — quotas, DLQ, backoff, checkpoints

## Orchestrator (CEO)

- [ ] 06-orchestrator-agent.mdc — CEO agent scaffold and wiring
- [ ] 06-orchestrator-plan-daily-run.mdc — planning tool
- [ ] 06-orchestrator-dispatch.mdc — dispatch tools
- [ ] 06-orchestrator-policy-enforcement.mdc — enforce policies tool
- [ ] 06-orchestrator-dlq-management.mdc — DLQ tools
- [ ] 06-orchestrator-ops-reporting.mdc — emit run events (observability consumes)

## Scraper Agent

- [ ] 10-scraper-resolve-channel.mdc — handle → channel ID
- [ ] 11-scraper-list-uploads.mdc — discovery with checkpoints
- [ ] 12-scraper-read-sheet-extract.mdc — read/backfill links
- [ ] 13-scraper-save-metadata.mdc — store video metadata
- [ ] 14-scraper-enqueue-transcription.mdc — job enqueue
- [ ] 15-scraper-remove-sheet-rows.mdc — archive/remove rows

## Transcriber Agent

- [ ] 20-transcriber-get-audio.mdc — extract audio URLs
- [ ] 21-transcriber-submit-job.mdc — submit AssemblyAI job
- [ ] 22-transcriber-poll-store.mdc — poll, Drive store, Firestore metadata

## Summarizer Agent

- [ ] 30-summarizer-generate-short.mdc — short summary generation
- [ ] 31-summarizer-store-zep-drive.mdc — store to Zep and Drive
- [ ] 32-zep-integration.mdc — enhanced Zep integration

## Observability (formerly Assistant)

- [ ] 40-assistant-alerts.mdc — alerts framework (observability)
- [ ] 40-observability-ops-suite.mdc — quotas, DLQ trends, stuck jobs, daily summary, LLM metrics, alert engine
- [ ] 40-observability-send-error-alert-fix.mdc — fix tests for send_error_alert

## Cross-cutting

- [ ] 37-llm-observability.mdc — LLM config and observability
- [ ] 41-audit-logging.mdc — audit logging system
- [ ] 05-agent-tools.mdc — agent tools consolidation
