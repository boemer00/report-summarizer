from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional
from pathlib import Path
import os


class Settings(BaseSettings):
    # Google Drive Configuration
    google_service_account_path: Path = Field(
        ..., description="Path to Google service account JSON key file"
    )
    google_drive_folder_id: str = Field(
        ..., description="Google Drive folder ID to read documents from"
    )
    google_drive_output_folder_id: Optional[str] = Field(
        None, description="Google Drive folder ID to save reports to"
    )

    # New fields for specific sources
    pdf_reports_folder_id: Optional[str] = Field(
        None, description="Google Drive folder ID for PDF reports"
    )
    google_doc_id: Optional[str] = Field(
        None, description="Google Doc ID containing article URLs"
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model_embedding: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )
    openai_model_chat: str = Field(
        default="gpt-4o-mini", description="OpenAI chat model for processing"
    )
    openai_model_summarization: str = Field(
        default="gpt-4o", description="OpenAI model for final summarization"
    )

    # Processing Configuration
    chunk_size: int = Field(default=1000, description="Document chunk size")
    chunk_overlap: int = Field(default=200, description="Document chunk overlap")
    max_topics: int = Field(default=10, description="Maximum number of topics to identify")
    min_topic_size: int = Field(
        default=3, description="Minimum documents per topic"
    )
    # Topic mode configuration
    topic_mode: str = Field(
        default="thematic",
        description="Topic creation mode: 'thematic' (AI/Customer Journey/Digital Performance) or 'auto' (KMeans)"
    )
    thematic_threshold: float = Field(
        default=0.2,
        description="Similarity threshold for assigning chunks to thematic pillars"
    )
    audience_profile: str = Field(
        default=(
            "Considered-Purchase Brands: decisions with high stakes and emotional weight across B2B"
            " enterprise and premium/luxury B2C. Confidence, trust, empathy, and ROI drive choices;"
            " DX must be seamless, personalized, and confidence-building; buyers seek reassurance"
            " and proof across touchpoints; human connection in digital channels matters."
        ),
        description="Audience and ICP description used to condition summaries"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_key: Optional[str] = Field(None, description="API key for protection")

    # Report Configuration
    report_title: str = Field(
        default="Monthly Business Intelligence Report",
        description="Report title"
    )
    max_summary_length: int = Field(
        default=500, description="Maximum summary length per document"
    )
    executive_summary_length: int = Field(
        default=1500, description="Executive summary length"
    )

    # Synopsis Configuration
    synopsis_enable: bool = Field(
        default=True, description="Enable new pillar synopsis generation"
    )
    synopsis_selection_k: int = Field(
        default=12, description="Number of representative chunks to select per pillar"
    )
    synopsis_mmr_lambda: float = Field(
        default=0.5, description="MMR lambda for relevance vs novelty tradeoff"
    )
    synopsis_max_citations: int = Field(
        default=3, description="Max number of source citations to append"
    )
    synopsis_paragraphs: int = Field(
        default=2, description="Number of paragraphs in synopsis (1 or 2)"
    )

    # Scheduling
    schedule_cron: str = Field(
        default="0 0 1 * *", description="Cron expression for scheduling"
    )
    run_on_startup: bool = Field(
        default=False, description="Run pipeline on startup"
    )

    # PDF Export Configuration
    pdf_enabled: bool = Field(
        default=True, description="Whether to generate a PDF version of the report"
    )
    pdf_page_size: str = Field(
        default="A4", description="PDF page size (e.g., A4, Letter)"
    )
    pdf_orientation: str = Field(
        default="Portrait", description="PDF orientation (Portrait or Landscape)"
    )
    pdf_margins_mm: int = Field(
        default=10, description="PDF margins in millimeters"
    )
    wkhtmltopdf_path: Optional[str] = Field(
        default=None, description="Path to wkhtmltopdf binary if not on PATH"
    )

    @validator("google_service_account_path")
    def validate_service_account_path(cls, v):
        if not v.exists():
            raise ValueError(f"Service account file not found: {v}")
        return v

    @validator("google_drive_output_folder_id")
    def set_output_folder(cls, v, values):
        if v is None and "google_drive_folder_id" in values:
            return values["google_drive_folder_id"]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


settings = None

def init_settings():
    """Initialize settings from environment."""
    global settings
    settings = get_settings()
    return settings
