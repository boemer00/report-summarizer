import io
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError

import src.core.config as config
from src.core.models import Document, DocumentType

logger = logging.getLogger(__name__)


class DriveClient:
    """Google Drive client for document extraction and report upload."""

    def __init__(self, service_account_path: Optional[Path] = None):
        """Initialize Drive client with service account credentials."""
        # Ensure settings are initialized and available
        self.settings = config.settings or config.init_settings()
        self.service_account_path = service_account_path or self.settings.google_service_account_path
        self.service = self._build_service()

    def _build_service(self):
        """Build Google Drive service with authentication."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(self.service_account_path),
                scopes=['https://www.googleapis.com/auth/drive.readonly',
                        'https://www.googleapis.com/auth/drive.file']
            )
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"Failed to build Drive service: {e}")
            raise

    def list_folder_files(self, folder_id: str) -> List[Dict[str, Any]]:
        """List all files in a specific folder."""
        try:
            query = f"'{folder_id}' in parents and trashed = false"
            results = []
            page_token = None

            while True:
                response = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, webViewLink, createdTime, modifiedTime, size)",
                    pageToken=page_token,
                    pageSize=100
                ).execute()

                files = response.get('files', [])
                results.extend(files)

                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            logger.info(f"Found {len(results)} files in folder {folder_id}")
            return results

        except HttpError as e:
            logger.error(f"Error listing files: {e}")
            raise

    def download_file(self, file_id: str, file_name: str, mime_type: str) -> bytes:
        """Download a file from Google Drive."""
        try:
            # Handle Google Docs exports
            if mime_type == 'application/vnd.google-apps.document':
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            elif mime_type == 'application/vnd.google-apps.presentation':
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            else:
                request = self.service.files().get_media(fileId=file_id)

            file_data = io.BytesIO()
            downloader = MediaIoBaseDownload(file_data, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download {int(status.progress() * 100)}% complete for {file_name}")

            logger.info(f"Downloaded file: {file_name}")
            return file_data.getvalue()

        except HttpError as e:
            logger.error(f"Error downloading file {file_name}: {e}")
            raise

    def get_document_type(self, mime_type: str) -> Optional[DocumentType]:
        """Determine document type from MIME type."""
        mime_mapping = {
            'application/pdf': DocumentType.PDF,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DocumentType.DOCX,
            'application/msword': DocumentType.DOCX,
            'application/vnd.google-apps.document': DocumentType.DOCX,
            'text/plain': DocumentType.TEXT,
            'text/html': DocumentType.URL,
            'application/vnd.google-apps.spreadsheet': DocumentType.TEXT,
            'application/vnd.google-apps.presentation': DocumentType.PDF,
        }
        return mime_mapping.get(mime_type)

    def extract_documents(self, folder_id: Optional[str] = None) -> List[Document]:
        """Extract all documents from a Google Drive folder."""
        folder_id = folder_id or self.settings.google_drive_folder_id
        documents = []

        files = self.list_folder_files(folder_id)

        for file in files:
            doc_type = self.get_document_type(file['mimeType'])

            if not doc_type:
                logger.warning(f"Skipping unsupported file type: {file['name']} ({file['mimeType']})")
                continue

            try:
                # For URLs/shortcuts, just store the link
                if file['mimeType'] == 'application/vnd.google-apps.shortcut':
                    document = Document(
                        id=file['id'],
                        name=file['name'],
                        type=DocumentType.URL,
                        source=file.get('webViewLink', ''),
                        content="",  # Will be fetched later
                        metadata={
                            'mime_type': file['mimeType'],
                            'created_time': file.get('createdTime'),
                            'modified_time': file.get('modifiedTime'),
                        }
                    )
                else:
                    # Download the file
                    file_content = self.download_file(
                        file['id'],
                        file['name'],
                        file['mimeType']
                    )

                    document = Document(
                        id=file['id'],
                        name=file['name'],
                        type=doc_type,
                        source=f"drive://{file['id']}",
                        content="",  # Will be extracted by parser
                        metadata={
                            'mime_type': file['mimeType'],
                            'file_size': file.get('size'),
                            'created_time': file.get('createdTime'),
                            'modified_time': file.get('modifiedTime'),
                            'raw_content': file_content  # Store raw content for parsing
                        }
                    )

                documents.append(document)

            except Exception as e:
                logger.error(f"Failed to process file {file['name']}: {e}")
                continue

        logger.info(f"Extracted {len(documents)} documents from Drive")
        return documents

    def extract_pdf_reports(self, folder_id: Optional[str] = None) -> List[Document]:
        """Extract only PDF documents from a specific Google Drive folder."""
        folder_id = folder_id or self.settings.pdf_reports_folder_id
        documents = []

        files = self.list_folder_files(folder_id)

        # Filter for PDFs only
        pdf_files = [f for f in files if f['mimeType'] == 'application/pdf']
        logger.info(f"Found {len(pdf_files)} PDF files in folder {folder_id}")

        for file in pdf_files:
            try:
                # Download the PDF file
                file_content = self.download_file(
                    file['id'],
                    file['name'],
                    file['mimeType']
                )

                document = Document(
                    id=file['id'],
                    name=file['name'],
                    type=DocumentType.PDF,
                    source=f"drive://{file['id']}",
                    content="",  # Will be extracted by parser
                    metadata={
                        'source_type': 'pdf_report',
                        'mime_type': file['mimeType'],
                        'file_size': file.get('size'),
                        'created_time': file.get('createdTime'),
                        'modified_time': file.get('modifiedTime'),
                        'web_view_link': file.get('webViewLink'),
                        'raw_content': file_content  # Store raw content for parsing
                    }
                )

                documents.append(document)

            except Exception as e:
                logger.error(f"Failed to process PDF file {file['name']}: {e}")
                continue

        logger.info(f"Extracted {len(documents)} PDF reports from Drive")
        return documents

    def upload_report(self, report_path: Path, report_name: str,
                     folder_id: Optional[str] = None) -> str:
        """Upload a report to Google Drive."""
        folder_id = folder_id or self.settings.google_drive_output_folder_id

        try:
            file_metadata = {
                'name': report_name,
                'parents': [folder_id] if folder_id else []
            }

            media = MediaFileUpload(
                str(report_path),
                mimetype='text/html',
                resumable=True
            )

            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()

            logger.info(f"Report uploaded successfully: {file.get('webViewLink')}")
            return file.get('webViewLink', '')

        except HttpError as e:
            logger.error(f"Error uploading report: {e}")
            raise

    def upload_file(self, path: Path, name: str, mime_type: str,
                    folder_id: Optional[str] = None) -> str:
        """Upload an arbitrary file to Google Drive and return webViewLink."""
        folder_id = folder_id or self.settings.google_drive_output_folder_id
        try:
            file_metadata = {
                'name': name,
                'parents': [folder_id] if folder_id else []
            }
            media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            logger.info(f"File uploaded successfully: {file.get('webViewLink')}")
            return file.get('webViewLink', '')
        except HttpError as e:
            logger.error(f"Error uploading file: {e}")
            raise

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """Create a new folder in Google Drive."""
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id] if parent_id else []
            }

            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()

            logger.info(f"Created folder: {folder_name}")
            return folder.get('id')

        except HttpError as e:
            logger.error(f"Error creating folder: {e}")
            raise
