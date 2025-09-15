#!/usr/bin/env python3
"""
Monthly execution script for the document summarizer pipeline.
Can be run directly or scheduled via cron.

Example cron entry (runs on the 1st of each month at 2 AM):
0 2 1 * * /usr/bin/python3 /path/to/run_monthly.py
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import init_settings, settings
from src.pipeline import run_pipeline

# Configure logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def send_email_notification(result: dict, recipient_email: str = None):
    """Send email notification with pipeline results."""
    if not recipient_email:
        logger.info("No recipient email configured, skipping notification")
        return
    
    try:
        # Email configuration (you'll need to set these in environment variables)
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        
        if not sender_email or not sender_password:
            logger.warning("Email credentials not configured")
            return
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"Document Summarizer Report - {datetime.now().strftime('%B %Y')}"
        
        # Create body
        if result['success']:
            body = f"""
The monthly document summarization pipeline has completed successfully.

Summary:
- Documents Processed: {result.get('documents_processed', 0)}
- Topics Identified: {result.get('topics_identified', 0)}
- Execution Time: {result.get('execution_time', 0):.2f} seconds
- Report ID: {result.get('report_id', 'N/A')}

Report URL: {result.get('report_url', 'Not uploaded to Drive')}
Local Path: {result.get('report_path', 'N/A')}

The report has been generated and is available for review.
"""
        else:
            body = f"""
The monthly document summarization pipeline has failed.

Error: {result.get('error', 'Unknown error')}
Documents Processed: {result.get('documents_processed', 0)}

Please check the logs for more details.
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        logger.info(f"Notification email sent to {recipient_email}")
        
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("Starting monthly document summarization pipeline")
    logger.info(f"Execution time: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    try:
        # Initialize settings
        init_settings()
        
        # Run the pipeline
        logger.info("Initializing pipeline...")
        result = run_pipeline(
            folder_id=settings.google_drive_folder_id,
            output_folder_id=settings.google_drive_output_folder_id,
            save_to_drive=True
        )
        
        # Log results
        logger.info("Pipeline execution completed")
        logger.info(f"Result: {json.dumps(result, indent=2)}")
        
        # Save result to file
        result_file = log_dir / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Send email notification if configured
        notification_email = os.getenv("NOTIFICATION_EMAIL")
        if notification_email:
            send_email_notification(result, notification_email)
        
        # Exit with appropriate code
        if result['success']:
            logger.info("Pipeline completed successfully")
            sys.exit(0)
        else:
            logger.error(f"Pipeline failed: {result.get('error')}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        
        # Try to send error notification
        notification_email = os.getenv("NOTIFICATION_EMAIL")
        if notification_email:
            send_email_notification(
                {"success": False, "error": str(e)},
                notification_email
            )
        
        sys.exit(1)


if __name__ == "__main__":
    main()