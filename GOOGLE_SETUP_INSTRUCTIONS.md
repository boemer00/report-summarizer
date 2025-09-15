# Google Drive Setup Instructions

## Required vs Optional Fields

### REQUIRED Fields

1. **`GOOGLE_SERVICE_ACCOUNT_PATH`** - Path to your service account key
2. **`GOOGLE_DRIVE_OUTPUT_FOLDER_ID`** - Where reports will be saved

### OPTIONAL Fields

- **`GOOGLE_DRIVE_FOLDER_ID`** - Only needed if using original mode (not using specific sources)

## How to Get Each Value

### 1. GOOGLE_SERVICE_ACCOUNT_PATH

This is the JSON key file for your Google Cloud service account:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create a new one)
3. Navigate to **IAM & Admin** → **Service Accounts**
4. Click **Create Service Account** (or use existing)
5. Fill in details and click **Create**
6. Skip the optional permissions step
7. Click on the created service account
8. Go to **Keys** tab → **Add Key** → **Create New Key**
9. Choose **JSON** format
10. Save the downloaded file somewhere safe
11. Use the path to this file in your `.env`

Example:
```env
GOOGLE_SERVICE_ACCOUNT_PATH=/Users/yourname/keys/my-service-account.json
```

### 2. GOOGLE_DRIVE_FOLDER_ID & GOOGLE_DRIVE_OUTPUT_FOLDER_ID

To get any Google Drive folder ID:

1. Open the folder in Google Drive
2. Look at the URL in your browser
3. The ID is the string after `/folders/`

Example URL:
```
https://drive.google.com/drive/folders/1Qgg79iivV4AeQxVKSCcaFFizTny7xVar
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                       This is the folder ID
```

### 3. PDF_REPORTS_FOLDER_ID (Already Provided)

Your PDF reports folder:
- URL: https://drive.google.com/drive/folders/17R0_quKt_TYOTSbKWoxe1OxUvhERZpkf
- ID: `17R0_quKt_TYOTSbKWoxe1OxUvhERZpkf`

### 4. GOOGLE_DOC_ID (Already Provided)

Your Google Doc with URLs:
- URL: https://docs.google.com/document/d/1ewKDBN4B1xrte4OzYuWxDUHNl39w4Aoz6GwPcu5NSKw/edit
- ID: `1ewKDBN4B1xrte4OzYuWxDUHNl39w4Aoz6GwPcu5NSKw`

## Complete .env Example

```env
# Required
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/your-service-account-key.json
GOOGLE_DRIVE_OUTPUT_FOLDER_ID=1Qgg79iivV4AeQxVKSCcaFFizTny7xVar

# Optional (can use PDF folder ID here too)
GOOGLE_DRIVE_FOLDER_ID=17R0_quKt_TYOTSbKWoxe1OxUvhERZpkf

# Your specific sources
PDF_REPORTS_FOLDER_ID=17R0_quKt_TYOTSbKWoxe1OxUvhERZpkf
GOOGLE_DOC_ID=1ewKDBN4B1xrte4OzYuWxDUHNl39w4Aoz6GwPcu5NSKw

# OpenAI
OPENAI_API_KEY=your-openai-api-key
```

## Important: Grant Access

After creating your service account, you MUST share your resources with it:

1. Find the service account email in your JSON key file (look for `"client_email"`)
2. Share the following with that email:
   - Your PDF folder (view access)
   - Your Google Doc (view access)
   - Your output folder (edit access)

To share:
1. Right-click the folder/document in Google Drive
2. Click "Share"
3. Add the service account email
4. Set appropriate permissions
5. Click "Send"

## Enable Required APIs

In Google Cloud Console, enable:
1. **Google Drive API**
2. **Google Docs API**

Navigate to **APIs & Services** → **Library** and search for each API to enable them.

## Quick Test

After setup, test with:
```bash
python scripts/test_integration.py
```

This will verify:
- Service account can access the PDF folder
- Service account can read the Google Doc
- All configurations are correct