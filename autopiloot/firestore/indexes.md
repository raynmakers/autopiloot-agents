# Firestore Composite Index Definitions

This document defines the required composite indexes for optimal Firestore query performance in the Autopiloot system.

## Required Indexes

### 1. Videos Collection Index

**Purpose**: Efficiently query videos by status and publication date

**Index Definition**:

- Collection: `videos`
- Fields:
  - `status` (Ascending)
  - `published_at` (Descending)

**Query Patterns Supported**:

- Find recent videos by status
- Get pending videos ordered by publication date
- Status-based pagination with time ordering

**Firebase CLI Command**:

```bash
firebase firestore:indexes --add-field-override videos status ASC published_at DESC
```

**Index JSON Configuration**:

```json
{
  "collectionGroup": "videos",
  "queryScope": "COLLECTION",
  "fields": [
    {
      "fieldPath": "status",
      "order": "ASCENDING"
    },
    {
      "fieldPath": "published_at",
      "order": "DESCENDING"
    }
  ]
}
```

### 2. Summaries Collection Index

**Purpose**: Efficiently query summaries by creation date

**Index Definition**:

- Collection: `summaries`
- Fields:
  - `created_at` (Descending)

**Query Patterns Supported**:

- Get recent summaries in chronological order
- Time-based pagination
- Daily/weekly summary aggregation

**Firebase CLI Command**:

```bash
firebase firestore:indexes --add-field-override summaries created_at DESC
```

**Index JSON Configuration**:

```json
{
  "collectionGroup": "summaries",
  "queryScope": "COLLECTION",
  "fields": [
    {
      "fieldPath": "created_at",
      "order": "DESCENDING"
    }
  ]
}
```

### 3. Jobs Dead Letter Queue Index

**Purpose**: Query failed jobs by type and failure time

**Index Definition**:

- Collection: `jobs_deadletter`
- Fields:
  - `job_type` (Ascending)
  - `last_error_at` (Descending)

**Query Patterns Supported**:

- Find recent failures by job type
- Monitor failure patterns
- Retry failed jobs by priority

**Firebase CLI Command**:

```bash
firebase firestore:indexes --add-field-override jobs_deadletter job_type ASC last_error_at DESC
```

**Index JSON Configuration**:

```json
{
  "collectionGroup": "jobs_deadletter",
  "queryScope": "COLLECTION",
  "fields": [
    {
      "fieldPath": "job_type",
      "order": "ASCENDING"
    },
    {
      "fieldPath": "last_error_at",
      "order": "DESCENDING"
    }
  ]
}
```

### 4. Transcription Jobs Index

**Purpose**: Query transcription jobs by status and submission time

**Index Definition**:

- Collection: `jobs/transcription`
- Fields:
  - `status` (Ascending)
  - `submitted_at` (Descending)

**Query Patterns Supported**:

- Find pending transcription jobs
- Monitor job queue status
- Track processing times

**Firebase CLI Command**:

```bash
firebase firestore:indexes --add-field-override jobs/transcription status ASC submitted_at DESC
```

**Index JSON Configuration**:

```json
{
  "collectionGroup": "transcription",
  "queryScope": "COLLECTION",
  "fields": [
    {
      "fieldPath": "status",
      "order": "ASCENDING"
    },
    {
      "fieldPath": "submitted_at",
      "order": "DESCENDING"
    }
  ]
}
```

## Index Management

### Creating Indexes

1. **Via Firebase Console**: Navigate to Firestore > Indexes and create composite indexes manually
2. **Via Firebase CLI**: Use the commands provided above
3. **Via Index Configuration File**: Deploy indexes using `firestore.indexes.json`

### Index Configuration File

For automated deployment, add these to `firestore.indexes.json`:

```json
{
  "indexes": [
    {
      "collectionGroup": "videos",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "published_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "summaries",
      "queryScope": "COLLECTION",
      "fields": [{ "fieldPath": "created_at", "order": "DESCENDING" }]
    },
    {
      "collectionGroup": "jobs_deadletter",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "job_type", "order": "ASCENDING" },
        { "fieldPath": "last_error_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "transcription",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "submitted_at", "order": "DESCENDING" }
      ]
    }
  ]
}
```

### Deployment

Deploy indexes using Firebase CLI:

```bash
firebase deploy --only firestore:indexes
```

## Performance Considerations

- **Build Time**: Composite indexes can take time to build for existing data
- **Storage Cost**: Each index adds to storage costs
- **Write Performance**: More indexes can slightly impact write performance
- **Query Optimization**: Use exactly the index fields in query ordering

## Monitoring

Monitor index usage and performance in Firebase Console:

- Firestore > Usage tab for index storage metrics
- Query performance monitoring for slow queries
- Index build status and completion times
