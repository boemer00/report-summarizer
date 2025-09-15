#!/usr/bin/env python3
"""Run the pipeline with specific PDF folder and Google Doc sources."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from src.pipeline import get_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run the pipeline with specific sources."""
    logger.info("=" * 60)
    logger.info("Starting Document Summarization Pipeline")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        # Get the pipeline instance
        pipeline = get_pipeline()

        # Run with specific sources (PDFs from folder + URLs from Doc)
        logger.info("Running pipeline with specific sources:")
        logger.info("  - PDF reports from Google Drive folder")
        logger.info("  - Article URLs from Google Doc")

        result = pipeline.run(
            use_specific_sources=True,  # Use PDF folder and Google Doc
            save_to_drive=True  # Save the report to Google Drive
        )

        # Display results
        logger.info("=" * 60)
        logger.info("Pipeline Results")
        logger.info("=" * 60)

        if result['success']:
            logger.info("✓ Pipeline completed successfully!")
            logger.info(f"  - Report ID: {result['report_id']}")
            logger.info(f"  - Documents processed: {result['documents_processed']}")
            logger.info(f"  - Topics identified: {result['topics_identified']}")
            logger.info(f"  - Execution time: {result['execution_time']:.2f} seconds")
            logger.info(f"  - Local report: {result['report_path']}")

            if result.get('report_url'):
                logger.info(f"  - Google Drive URL: {result['report_url']}")

            # Get the generated report details
            report = pipeline.get_last_report()
            if report:
                logger.info("\nReport Details:")
                logger.info(f"  - Title: {report.title}")
                logger.info(f"  - Period: {report.period_start} to {report.period_end}")
                logger.info(f"  - Topics:")
                for i, topic in enumerate(report.topics, 1):
                    logger.info(f"    {i}. {topic.name} ({len(topic.document_ids)} documents)")

        else:
            logger.error("✗ Pipeline failed!")
            logger.error(f"  - Error: {result['error']}")
            logger.error(f"  - Documents processed: {result.get('documents_processed', 0)}")
            logger.error(f"  - Topics identified: {result.get('topics_identified', 0)}")

        return 0 if result['success'] else 1

    except Exception as e:
        logger.error(f"Fatal error running pipeline: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())