# Document Summarizer - Monthly Business Intelligence Report Generator

An automated MVP solution that extracts documents from Google Drive, identifies key topics, and generates comprehensive business intelligence reports using AI.

## Features

- **Automated Document Extraction**: Pulls documents from Google Drive folders
- **Multi-Format Support**: Handles PDF, DOCX, URLs, and text files
- **AI-Powered Topic Identification**: Uses embeddings and clustering to identify main topics
- **Smart Summarization**: Generates topic-based summaries and executive summaries
- **Beautiful Reports**: Creates HTML reports with professional formatting
- **Flexible Scheduling**: Run monthly via cron or built-in scheduler
- **REST API**: FastAPI service for manual triggers and monitoring
- **Docker Support**: Easy deployment with Docker Compose

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌────────────────┐
│  Google Drive   │────▶│   Extractor  │────▶│     Parser     │
│    Documents    │     │              │     │  (PDF/DOCX/URL)│
└─────────────────┘     └──────────────┘     └────────────────┘
                                                      │
                                                      ▼
┌─────────────────┐     ┌──────────────┐     ┌────────────────┐
│   HTML Report   │◀────│  Summarizer  │◀────│   Embeddings   │
│  (Google Drive) │     │  (LangChain) │     │    (OpenAI)    │
└─────────────────┘     └──────────────┘     └────────────────┘
                                                      │
                                                      ▼
                        ┌──────────────┐     ┌────────────────┐
                        │    Topics    │◀────│  Vector Store  │
                        │  (Clustering)│     │    (FAISS)     │
                        └──────────────┘     └────────────────┘
```

## Prerequisites

- Python 3.11+
- Google Cloud Service Account with Drive API access
- OpenAI API key
- Docker and Docker Compose (optional)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/report-summarizer.git
cd report-summarizer
```

### 2. Set Up Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Drive API
4. Create a service account:
   - Go to IAM & Admin > Service Accounts
   - Create new service account
   - Download JSON key file
5. Share your Google Drive folder with the service account email

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Google Drive Configuration
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/service-account-key.json
GOOGLE_DRIVE_FOLDER_ID=your-drive-folder-id
GOOGLE_DRIVE_OUTPUT_FOLDER_ID=your-output-folder-id

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Optional: API Protection
API_KEY=your-api-key-for-protection
```

### 4. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Run the Service

#### Option A: FastAPI Service

```bash
uvicorn src.api.main:app --reload
```

Access the API at `http://localhost:8000`

#### Option B: Direct Pipeline Execution

```bash
python scripts/run_monthly.py
```

#### Option C: Docker Compose

```bash
docker-compose up -d
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information and available endpoints |
| `/health` | GET | Health check |
| `/trigger` | POST | Trigger pipeline execution |
| `/status` | GET | Get pipeline status |
| `/topics` | GET | Get identified topics from last run |
| `/report` | GET | Get last report metadata |
| `/report/download` | GET | Download last report as HTML |
| `/clear-cache` | POST | Clear vector store cache |
| `/config` | GET | Get current configuration |

### Example API Usage

```bash
# Trigger pipeline
curl -X POST http://localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "folder_id": "optional-folder-id",
    "save_to_drive": true
  }'

# Check status
curl http://localhost:8000/status \
  -H "X-API-Key: your-api-key"
```

## Scheduling

### Option 1: Cron (Linux/Mac)

Add to crontab (`crontab -e`):

```bash
# Run on the 1st of each month at 2 AM
0 2 1 * * /usr/bin/python3 /path/to/report_summarizer/scripts/run_monthly.py
```

### Option 2: Built-in Scheduler

```bash
python scripts/scheduler.py
```

### Option 3: Docker Scheduler

The Docker Compose setup includes a scheduler service that runs automatically.

## Configuration Options

Key settings in `.env`:

- `CHUNK_SIZE`: Document chunk size for embeddings (default: 1000)
- `MAX_TOPICS`: Maximum number of topics to identify (default: 10)
- `MIN_TOPIC_SIZE`: Minimum documents per topic (default: 3)
- `OPENAI_MODEL_EMBEDDING`: Embedding model (default: text-embedding-3-small)
- `OPENAI_MODEL_CHAT`: Chat model for processing (default: gpt-4o-mini)
- `OPENAI_MODEL_SUMMARIZATION`: Model for final summaries (default: gpt-4o)

## Output

Reports are generated in HTML format with:
- Executive summary
- Topic analysis with summaries
- Document statistics
- Professional styling

Reports are saved to:
- Local: `reports/report_YYYYMMDD_HHMMSS.html`
- Google Drive: Uploaded to specified output folder

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ scripts/
flake8 src/ scripts/
mypy src/
```

## Troubleshooting

### Common Issues

1. **Google Drive Authentication Error**
   - Ensure service account has access to the folder
   - Check service account JSON path is correct

2. **OpenAI Rate Limits**
   - Reduce `CHUNK_SIZE` to process fewer embeddings
   - Use smaller models for testing

3. **Out of Memory**
   - Reduce document batch size
   - Use `faiss-cpu` instead of GPU version

## Extending the System

The architecture is designed for easy extension:

- **Add Document Formats**: Extend `DocumentParser` class
- **Custom Topics**: Modify `TopicClusterer` for domain-specific clustering
- **Report Formats**: Add new templates in `ReportGenerator`
- **Integrations**: Add new extractors for other data sources

## License

MIT License - see LICENSE file for details

## Support

For issues or questions, please create an issue in the GitHub repository.
