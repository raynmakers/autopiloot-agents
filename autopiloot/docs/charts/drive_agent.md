## Drive Agent — Google Drive Content Ingestion Pipeline

```mermaid
flowchart TD
  subgraph Config
    CFG[settings.yaml<br/>drive_agent.targets]
  end

  subgraph DriveAPI[Google Drive API]
    DRIVES[(Drive Files)]
    CHANGES[Changes API]
    EXPORT[Export API]
  end

  subgraph DriveAgent
    LTC[ListTrackedTargetsFromConfig]
    RFT[ResolveFolderTree]
    LDC[ListDriveChanges]
    FFC[FetchFileContent]
    ETD[ExtractTextFromDocument]
    UDD[UpsertDriveDocsToZep]
    SDR[SaveDriveIngestionRecord]
  end

  subgraph Processing
    PDF[PDF Extraction<br/>PyPDF2]
    DOCX[DOCX Extraction<br/>python-docx]
    HTML[HTML Extraction<br/>BeautifulSoup]
    CSV[CSV Processing<br/>pandas]
    TXT[Plain Text]
  end

  subgraph Storage
    ZEP[(Zep GraphRAG<br/>Semantic Search)]
    FS[(Firestore<br/>Audit Logs)]
  end

  %% Configuration flow
  CFG --> LTC
  LTC --> RFT
  LTC --> LDC

  %% Drive API interactions
  RFT --> DRIVES
  LDC --> CHANGES
  FFC --> DRIVES
  FFC --> EXPORT

  %% Content processing pipeline
  RFT --> FFC
  LDC --> FFC
  FFC --> ETD

  %% Format-specific extraction
  ETD --> PDF
  ETD --> DOCX
  ETD --> HTML
  ETD --> CSV
  ETD --> TXT

  %% Text aggregation and storage
  PDF --> UDD
  DOCX --> UDD
  HTML --> UDD
  CSV --> UDD
  TXT --> UDD

  %% Final storage
  UDD --> ZEP
  UDD --> SDR
  SDR --> FS

  %% Scheduling (every 3 hours)
  SCHED[Firebase Functions<br/>Every 3 hours] --> LTC

  %% Styling
  classDef agent fill:#e1f5fe,stroke:#0277bd,color:#01579b;
  classDef storage fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c;
  classDef processing fill:#fff3e0,stroke:#f57c00,color:#e65100;
  classDef config fill:#e8f5e8,stroke:#388e3c,color:#1b5e20;

  class DriveAgent agent;
  class ZEP,FS storage;
  class PDF,DOCX,HTML,CSV,TXT processing;
  class CFG config;
```

### Key Features

- **Incremental Processing**: Uses Google Drive Changes API with checkpoint tokens
- **Multi-Format Support**: PDF, DOCX, HTML, CSV, and plain text extraction
- **Google Workspace Integration**: Automatic export of Docs to DOCX, Sheets to CSV
- **Pattern Filtering**: fnmatch-based include/exclude patterns per target
- **Semantic Indexing**: Document chunking and Zep GraphRAG integration
- **Audit Logging**: Comprehensive Firestore logging with performance metrics
- **Scheduled Execution**: Automated 3-hour sync via Firebase Functions

### Processing Pipeline

1. **Configuration**: Load Drive targets from settings.yaml
2. **Discovery**: Resolve folder structure or detect incremental changes
3. **Fetching**: Download file content with format-specific handling
4. **Extraction**: Multi-format text extraction with encoding detection
5. **Indexing**: Document chunking and Zep GraphRAG upsert
6. **Auditing**: Comprehensive Firestore logging with metrics

### Supported Formats

- **PDF**: PyPDF2 for text extraction
- **DOCX**: python-docx for document processing
- **HTML**: BeautifulSoup for web content
- **CSV**: pandas for structured data
- **Plain Text**: Direct UTF-8 processing
- **Google Workspace**: Automatic format conversion