# Quick Setup Guide

## Step 1: Create .env file

Create a `.env` file in the project root with your credentials:

```env
# Google Drive Configuration
GOOGLE_SERVICE_ACCOUNT_PATH=path/to/your-service-account-key.json
GOOGLE_DRIVE_FOLDER_ID=your-default-folder-id
GOOGLE_DRIVE_OUTPUT_FOLDER_ID=your-output-folder-id

# Your specific sources
PDF_REPORTS_FOLDER_ID=17R0_quKt_TYOTSbKWoxe1OxUvhERZpkf
GOOGLE_DOC_ID=1ewKDBN4B1xrte4OzYuWxDUHNl39w4Aoz6GwPcu5NSKw

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Optional API protection
API_KEY=your-api-key-if-needed
```

## Step 2: Grant Access

Share the following with your service account email:
1. Google Drive folder: https://drive.google.com/drive/folders/17R0_quKt_TYOTSbKWoxe1OxUvhERZpkf
2. Google Doc: https://docs.google.com/document/d/1ewKDBN4B1xrte4OzYuWxDUHNl39w4Aoz6GwPcu5NSKw

Find your service account email in the JSON key file (look for "client_email").

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 4: Test the Integration

```bash
# Test that everything is working
python scripts/test_integration.py
```

## Step 5: Run the Pipeline

```bash
# Process PDFs and URLs, generate report
python scripts/run_specific_sources.py
```

Or use the API:

```bash
# Start API server
uvicorn src.api.main:app --reload

# In another terminal, trigger the pipeline
curl -X POST http://localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"use_specific_sources": true}'
```

## What Happens

1. **Extracts** PDF reports from your Google Drive folder
2. **Fetches** article URLs from your Google Doc
3. **Processes** all documents (PDFs + web articles)
4. **Identifies** key topics using AI clustering
5. **Generates** comprehensive summaries
6. **Creates** HTML report with insights
7. **Uploads** report back to Google Drive

## Output

- Local report: `reports/report_[timestamp].html`
- Google Drive: Check your output folder for the uploaded report

## Need Help?

- Check `INTEGRATION_GUIDE.md` for detailed documentation
- Review logs for any errors
- Ensure all permissions are correctly set