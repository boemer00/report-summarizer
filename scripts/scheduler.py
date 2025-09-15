#!/usr/bin/env python3
"""
Alternative scheduler for running the pipeline periodically.
Uses the schedule library instead of cron for cross-platform compatibility.
"""

import sys
from pathlib import Path
import schedule
import time
import logging
from datetime import datetime
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import init_settings, settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_pipeline_job():
    """Execute the pipeline script."""
    try:
        logger.info("Starting scheduled pipeline execution")
        
        # Run the monthly script
        script_path = Path(__file__).parent / "run_monthly.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Pipeline executed successfully")
        else:
            logger.error(f"Pipeline failed with return code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Failed to execute pipeline: {e}")


def main():
    """Main scheduler loop."""
    # Initialize settings
    init_settings()
    
    logger.info("Starting document summarizer scheduler")
    logger.info(f"Schedule: {settings.schedule_cron}")
    
    # Run on startup if configured
    if settings.run_on_startup:
        logger.info("Running pipeline on startup as configured")
        run_pipeline_job()
    
    # Schedule monthly execution (on the 1st at 00:00)
    schedule.every().month.at("00:00").do(run_pipeline_job)
    
    # Alternative scheduling options (uncomment as needed):
    # schedule.every().day.at("02:00").do(run_pipeline_job)  # Daily at 2 AM
    # schedule.every().week.at("00:00").do(run_pipeline_job)  # Weekly on Monday at midnight
    # schedule.every(30).days.do(run_pipeline_job)  # Every 30 days
    
    logger.info("Scheduler is running. Press Ctrl+C to stop.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()