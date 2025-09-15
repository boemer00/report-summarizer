from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
from pathlib import Path
from datetime import datetime

import src.core.config as config
from src.pipeline import get_pipeline

app = FastAPI(
    title="Document Summarizer API",
    description="API for automated document summarization and report generation",
    version="1.0.0"
)

# Global pipeline instance
pipeline = get_pipeline()


class TriggerRequest(BaseModel):
    folder_id: Optional[str] = None
    output_folder_id: Optional[str] = None
    save_to_drive: bool = True
    use_specific_sources: bool = True  # Use PDF folder and Google Doc by default


class TriggerResponse(BaseModel):
    message: str
    job_id: str
    status: str


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify API key if configured."""
    active_settings = config.settings or config.init_settings()
    if active_settings.api_key:
        if not x_api_key or x_api_key != active_settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Document Summarizer API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "GET /health": "Health check",
            "POST /trigger": "Trigger pipeline execution",
            "GET /status": "Get pipeline status",
            "GET /topics": "Get identified topics from last run",
            "GET /report": "Get last generated report",
            "GET /report/download": "Download last report as HTML"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "pipeline_status": pipeline.get_status()["status"]
    }


async def run_pipeline_async(folder_id: Optional[str],
                            output_folder_id: Optional[str],
                            save_to_drive: bool,
                            use_specific_sources: bool):
    """Run pipeline asynchronously."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        pipeline.run,
        folder_id,
        output_folder_id,
        save_to_drive,
        use_specific_sources
    )
    return result


@app.post("/trigger", response_model=TriggerResponse)
async def trigger_pipeline(
    request: TriggerRequest,
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_api_key)
):
    """Trigger the document summarization pipeline."""
    # Check if pipeline is already running
    status = pipeline.get_status()
    if status["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running"
        )

    # Start pipeline in background
    background_tasks.add_task(
        run_pipeline_async,
        request.folder_id,
        request.output_folder_id,
        request.save_to_drive,
        request.use_specific_sources
    )

    # Generate job ID (using timestamp for simplicity)
    job_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    return TriggerResponse(
        message="Pipeline triggered successfully",
        job_id=job_id,
        status="started"
    )


@app.get("/status")
async def get_pipeline_status(authenticated: bool = Depends(verify_api_key)):
    """Get current pipeline status."""
    return pipeline.get_status()


@app.get("/topics")
async def get_topics(authenticated: bool = Depends(verify_api_key)):
    """Get identified topics from the last pipeline run."""
    report = pipeline.get_last_report()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="No report available. Run the pipeline first."
        )

    return {
        "report_id": report.id,
        "topics_count": len(report.topics),
        "topics": [
            {
                "id": topic.id,
                "name": topic.name,
                "description": topic.description,
                "document_count": len(topic.document_ids),
                "summary": topic.summary[:500] if topic.summary else None
            }
            for topic in report.topics
        ]
    }


@app.get("/report")
async def get_report(authenticated: bool = Depends(verify_api_key)):
    """Get the last generated report metadata."""
    report = pipeline.get_last_report()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="No report available. Run the pipeline first."
        )

    return {
        "report_id": report.id,
        "title": report.title,
        "created_at": report.created_at.isoformat(),
        "period": {
            "start": report.period_start.isoformat(),
            "end": report.period_end.isoformat()
        },
        "document_count": report.document_count,
        "topics_count": len(report.topics),
        "executive_summary": report.executive_summary
    }


@app.get("/report/download")
async def download_report(authenticated: bool = Depends(verify_api_key)):
    """Download the last generated report as HTML."""
    # Find the most recent report file
    reports_dir = Path("reports")

    if not reports_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="No reports directory found"
        )

    report_files = list(reports_dir.glob("report_*.html"))

    if not report_files:
        raise HTTPException(
            status_code=404,
            detail="No report files found"
        )

    # Get the most recent report
    latest_report = max(report_files, key=lambda p: p.stat().st_mtime)

    return FileResponse(
        path=str(latest_report),
        media_type="text/html",
        filename=latest_report.name
    )


@app.post("/clear-cache")
async def clear_cache(authenticated: bool = Depends(verify_api_key)):
    """Clear the vector store cache."""
    pipeline.clear_cache()
    return {"message": "Cache cleared successfully"}


@app.get("/config")
async def get_config(authenticated: bool = Depends(verify_api_key)):
    """Get current configuration (non-sensitive values only)."""
    s = config.settings or config.init_settings()
    return {
        "chunk_size": s.chunk_size,
        "chunk_overlap": s.chunk_overlap,
        "max_topics": s.max_topics,
        "min_topic_size": s.min_topic_size,
        "report_title": s.report_title,
        "max_summary_length": s.max_summary_length,
        "executive_summary_length": s.executive_summary_length,
        "schedule_cron": s.schedule_cron,
        "models": {
            "embedding": s.openai_model_embedding,
            "chat": s.openai_model_chat,
            "summarization": s.openai_model_summarization
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
