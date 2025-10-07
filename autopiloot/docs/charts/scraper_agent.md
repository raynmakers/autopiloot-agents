## Scraper Agent — Workflow

```mermaid
flowchart TD
  A[Schedule 01:00 CET] --> RH[ResolveChannelHandles]
  RH --> B[ListRecentUploads]
  A --> C[ReadSheetLinks]
  C --> D[ExtractYouTubeFromPage]
  B --> E[SaveVideoMetadata]
  D --> E
  E --> F{Eligible? <= 70min}
  F -- yes --> G[EnqueueTranscription]
  F -- no --> H[Audit: Skipped]
  G --> I[Status: transcription_queued]
  I --> J[RemoveSheetRow (backfill)]
```
