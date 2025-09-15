import logging
import re
from typing import List, Optional, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import src.core.config as config
from src.core.models import Document, DocumentType

logger = logging.getLogger(__name__)


class DocsClient:
    """Google Docs client for extracting content and URLs from documents."""

    def __init__(self, service_account_path: Optional[str] = None):
        """Initialize Docs client with service account credentials."""
        # Ensure settings are initialized and available
        self.settings = config.settings or config.init_settings()
        self.service_account_path = service_account_path or self.settings.google_service_account_path
        self.service = self._build_service()

    def _build_service(self):
        """Build Google Docs service with authentication."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(self.service_account_path),
                scopes=[
                    'https://www.googleapis.com/auth/documents.readonly',
                    'https://www.googleapis.com/auth/drive.readonly'
                ]
            )
            return build('docs', 'v1', credentials=credentials)
        except Exception as e:
            logger.error(f"Failed to build Docs service: {e}")
            raise

    def get_document(self, document_id: str) -> Dict[str, Any]:
        """Fetch a Google Doc by its ID."""
        try:
            document = self.service.documents().get(documentId=document_id).execute()
            logger.info(f"Retrieved document: {document.get('title', 'Untitled')}")
            return document
        except HttpError as e:
            logger.error(f"Error fetching document {document_id}: {e}")
            raise

    def extract_text_from_document(self, document: Dict[str, Any]) -> str:
        """Extract plain text content from a Google Doc."""
        text_content = []

        content = document.get('body', {}).get('content', [])

        for element in content:
            if 'paragraph' in element:
                paragraph = element['paragraph']
                for text_element in paragraph.get('elements', []):
                    if 'textRun' in text_element:
                        text = text_element['textRun'].get('content', '')
                        text_content.append(text)

        full_text = ''.join(text_content)
        logger.info(f"Extracted {len(full_text)} characters of text")
        return full_text

    def extract_urls_from_text(self, text: str) -> List[str]:
        """Extract URLs from text content."""
        # Multiple URL patterns to catch different formats
        url_patterns = [
            # Standard URLs with protocol
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            # URLs in parentheses or brackets
            r'(?<=\()[https?://][^\s)]+',
            r'(?<=\[)[https?://][^\s\]]+',
            # www URLs without protocol
            r'(?:^|\s)(www\.[^\s<>"{}|\\^`\[\]]+)',
        ]

        urls = []
        for pattern in url_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the URL
                url = match.strip()
                # Add protocol if missing
                if url.startswith('www.'):
                    url = 'https://' + url
                # Remove trailing punctuation
                url = re.sub(r'[.,;:!?\'")\]}>]+$', '', url)
                if url and url not in urls:
                    urls.append(url)

        # Filter out obviously invalid URLs
        valid_urls = []
        for url in urls:
            # Basic validation
            if len(url) > 10 and '.' in url:
                valid_urls.append(url)

        logger.info(f"Extracted {len(valid_urls)} unique URLs from document")
        return valid_urls

    def extract_urls_from_document(self, document_id: str) -> List[str]:
        """Extract all URLs from a Google Doc."""
        try:
            # Get the document
            document = self.get_document(document_id)

            # Extract text content
            text_content = self.extract_text_from_document(document)

            # Extract URLs from text
            urls = self.extract_urls_from_text(text_content)

            # Also check for hyperlinks in the document
            hyperlinks = self._extract_hyperlinks_from_document(document)

            # Combine and deduplicate
            all_urls = list(set(urls + hyperlinks))

            logger.info(f"Total unique URLs found: {len(all_urls)}")
            return all_urls

        except Exception as e:
            logger.error(f"Error extracting URLs from document {document_id}: {e}")
            raise

    def _extract_hyperlinks_from_document(self, document: Dict[str, Any]) -> List[str]:
        """Extract hyperlinked URLs from a Google Doc."""
        hyperlinks = []

        content = document.get('body', {}).get('content', [])

        for element in content:
            if 'paragraph' in element:
                paragraph = element['paragraph']
                for text_element in paragraph.get('elements', []):
                    if 'textRun' in text_element:
                        text_run = text_element['textRun']
                        text_style = text_run.get('textStyle', {})
                        link = text_style.get('link', {})
                        url = link.get('url')
                        if url:
                            hyperlinks.append(url)

        unique_hyperlinks = list(set(hyperlinks))
        logger.info(f"Found {len(unique_hyperlinks)} unique hyperlinks")
        return unique_hyperlinks

    def create_url_documents(self, document_id: str) -> List[Document]:
        """Create Document objects for URLs extracted from a Google Doc."""
        urls = self.extract_urls_from_document(document_id)

        documents = []
        for i, url in enumerate(urls):
            # Create a Document object for each URL
            doc = Document(
                id=f"doc_url_{i}_{hash(url)}",
                name=f"Article from URL: {url[:50]}...",
                type=DocumentType.URL,
                source=url,
                content="",  # Will be fetched by the parser
                metadata={
                    'source_type': 'google_doc_url',
                    'source_document_id': document_id,
                    'url_index': i
                }
            )
            documents.append(doc)

        logger.info(f"Created {len(documents)} Document objects from URLs")
        return documents
