#!/usr/bin/env python3
"""Test script to verify Google Drive and Docs integration."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import src.core.config as config
from src.extractors.drive_client import DriveClient
from src.extractors.docs_client import DocsClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_pdf_extraction():
    """Test extracting PDFs from the specified Drive folder."""
    logger.info("=" * 60)
    logger.info("Testing PDF extraction from Google Drive")
    logger.info("=" * 60)

    try:
        drive_client = DriveClient()
        cfg = config.settings or config.init_settings()

        if cfg.pdf_reports_folder_id:
            logger.info(f"Folder ID: {cfg.pdf_reports_folder_id}")
            pdf_documents = drive_client.extract_pdf_reports(cfg.pdf_reports_folder_id)

            logger.info(f"\nFound {len(pdf_documents)} PDF documents:")
            for doc in pdf_documents:
                logger.info(f"  - {doc.name}")
                logger.info(f"    ID: {doc.id}")
                logger.info(f"    Type: {doc.type}")
                logger.info(f"    Source: {doc.source}")
                logger.info(f"    Metadata: {list(doc.metadata.keys())}")

            return True
        else:
            logger.warning("PDF_REPORTS_FOLDER_ID not configured in environment")
            return False

    except Exception as e:
        logger.error(f"Error testing PDF extraction: {e}")
        return False


def test_url_extraction():
    """Test extracting URLs from the Google Doc."""
    logger.info("=" * 60)
    logger.info("Testing URL extraction from Google Doc")
    logger.info("=" * 60)

    try:
        docs_client = DocsClient()
        cfg = config.settings or config.init_settings()

        if cfg.google_doc_id:
            logger.info(f"Document ID: {cfg.google_doc_id}")

            # First, test getting the document
            document = docs_client.get_document(cfg.google_doc_id)
            logger.info(f"Document title: {document.get('title', 'Untitled')}")

            # Extract URLs
            urls = docs_client.extract_urls_from_document(cfg.google_doc_id)
            logger.info(f"\nFound {len(urls)} URLs:")
            for i, url in enumerate(urls, 1):
                logger.info(f"  {i}. {url}")

            # Create document objects
            url_documents = docs_client.create_url_documents(cfg.google_doc_id)
            logger.info(f"\nCreated {len(url_documents)} Document objects for processing")

            return True
        else:
            logger.warning("GOOGLE_DOC_ID not configured in environment")
            return False

    except Exception as e:
        logger.error(f"Error testing URL extraction: {e}")
        return False


def test_combined_extraction():
    """Test extracting from both sources together."""
    logger.info("=" * 60)
    logger.info("Testing combined extraction from both sources")
    logger.info("=" * 60)

    try:
        drive_client = DriveClient()
        docs_client = DocsClient()
        cfg = config.settings or config.init_settings()

        total_documents = []

        # Get PDFs
        if cfg.pdf_reports_folder_id:
            pdf_documents = drive_client.extract_pdf_reports(cfg.pdf_reports_folder_id)
            total_documents.extend(pdf_documents)
            logger.info(f"Added {len(pdf_documents)} PDF documents")

        # Get URLs
        if cfg.google_doc_id:
            url_documents = docs_client.create_url_documents(cfg.google_doc_id)
            total_documents.extend(url_documents)
            logger.info(f"Added {len(url_documents)} URL documents")

        logger.info(f"\nTotal documents for processing: {len(total_documents)}")

        # Show summary by source type
        pdf_count = sum(1 for d in total_documents if d.metadata.get('source_type') == 'pdf_report')
        url_count = sum(1 for d in total_documents if d.metadata.get('source_type') == 'google_doc_url')

        logger.info(f"\nDocument breakdown:")
        logger.info(f"  - PDF reports: {pdf_count}")
        logger.info(f"  - Web articles: {url_count}")

        return True

    except Exception as e:
        logger.error(f"Error testing combined extraction: {e}")
        return False


def main():
    """Run all integration tests."""
    logger.info("Starting Google integration tests")
    logger.info("=" * 60)

    # Initialize settings
    try:
        config.init_settings()
        logger.info("Settings initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize settings: {e}")
        logger.error("Make sure your .env file is properly configured")
        return 1

    # Run tests
    tests_passed = []

    # Test PDF extraction
    tests_passed.append(test_pdf_extraction())

    # Test URL extraction
    tests_passed.append(test_url_extraction())

    # Test combined extraction
    tests_passed.append(test_combined_extraction())

    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    logger.info(f"PDF Extraction: {'✓ PASSED' if tests_passed[0] else '✗ FAILED'}")
    logger.info(f"URL Extraction: {'✓ PASSED' if tests_passed[1] else '✗ FAILED'}")
    logger.info(f"Combined Extraction: {'✓ PASSED' if tests_passed[2] else '✗ FAILED'}")

    if all(tests_passed):
        logger.info("\n✓ All tests passed! The integration is working correctly.")
        return 0
    else:
        logger.error("\n✗ Some tests failed. Please check the configuration and logs.")
        return 1


if __name__ == "__main__":
    exit(main())
