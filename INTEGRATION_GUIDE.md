# Google Drive & Docs Integration Guide

## Overview

This document describes the integration with Google Drive for PDF reports and Google Docs for article URLs.

## New Features

### 1. PDF Reports from Specific Drive Folder
- Extracts PDF documents only from a designated Google Drive folder
- Processes PDF content for analysis and summarization
- Maintains metadata about source type

### 2. Article URLs from Google Doc
- Fetches and parses a Google Doc containing article URLs
- Extracts all URLs from the document (both plain text and hyperlinks)
- Creates document objects for each URL for web scraping

## Configuration

### Required Environment Variables

Add these to your `.env` file:

```env
# Specific source configurations
PDF_REPORTS_FOLDER_ID=17R0_quKt_TYOTSbKWoxe1OxUvhERZpkf
GOOGLE_DOC_ID=1ewKDBN4B1xrte4OzYuWxDUHNl39w4Aoz6GwPcu5NSKw
```

### Google API Permissions

Ensure your service account has access to:
1. The Google Drive folder containing PDF reports
2. The Google Doc containing article URLs
3. Google Docs API (for reading document content)

## Usage

### Using the Test Script

Test the integration without running the full pipeline:

```bash
python scripts/test_integration.py
```

This will:
- Test PDF extraction from the Drive folder
- Test URL extraction from the Google Doc
- Verify combined extraction works

### Running the Full Pipeline

#### Option 1: Command Line Script

```bash
python scripts/run_specific_sources.py
```

This runs the pipeline with the specific PDF folder and Google Doc sources.

#### Option 2: API Endpoint

```bash
# Start the API
uvicorn src.api.main:app --reload

# Trigger pipeline with specific sources
curl -X POST http://localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "use_specific_sources": true,
    "save_to_drive": true
  }'
```

#### Option 3: Python Code

```python
from src.pipeline import get_pipeline

pipeline = get_pipeline()
result = pipeline.run(
    use_specific_sources=True,  # Use PDF folder and Google Doc
    save_to_drive=True
)
```

## Pipeline Parameters

The `pipeline.run()` method now accepts:

- `use_specific_sources` (bool):
  - `True`: Use PDF folder and Google Doc (new behavior)
  - `False`: Use regular Drive folder (original behavior)
- `folder_id` (str, optional): Override default folder ID
- `output_folder_id` (str, optional): Override output folder ID
- `save_to_drive` (bool): Whether to upload report to Drive

## Architecture

### New Components

1. **DocsClient** (`src/extractors/docs_client.py`)
   - Handles Google Docs API interactions
   - Extracts text and URLs from documents
   - Creates Document objects for URLs

2. **Enhanced DriveClient** (`src/extractors/drive_client.py`)
   - New `extract_pdf_reports()` method
   - Filters for PDF files only
   - Adds source metadata

### Data Flow

```
PDF Reports (Drive Folder) ─┐
                             ├─→ Combined Documents → Processing Pipeline → Report
Article URLs (Google Doc) ──┘
```

## Document Metadata

Documents now include source tracking:

- PDF Reports: `metadata['source_type'] = 'pdf_report'`
- Article URLs: `metadata['source_type'] = 'google_doc_url'`

This allows for:
- Source-specific processing
- Grouped reporting by source type
- Debugging and tracking

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Ensure service account has access to both the Drive folder and Google Doc
   - Share resources with the service account email

2. **No URLs Found**
   - Check that URLs in the Google Doc are properly formatted
   - Verify the Doc ID is correct

3. **PDFs Not Downloading**
   - Confirm the folder contains PDF files
   - Check folder ID is correct
   - Verify Drive API is enabled

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

Potential improvements:
- Filter PDFs by date range
- Support multiple Google Docs
- URL validation and deduplication
- Parallel processing for faster extraction
- Caching for frequently accessed documents