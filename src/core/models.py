from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    URL = "url"
    TEXT = "text"


class Document(BaseModel):
    id: str = Field(..., description="Unique document identifier")
    name: str = Field(..., description="Document name")
    type: DocumentType = Field(..., description="Document type")
    source: str = Field(..., description="Source path or URL")
    content: str = Field(..., description="Extracted text content")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    chunk_ids: List[str] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    content: str = Field(..., description="Chunk text content")
    embedding: Optional[List[float]] = Field(None, description="Embedding vector")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Topic(BaseModel):
    id: str = Field(..., description="Topic identifier")
    name: str = Field(..., description="Topic name")
    description: str = Field(..., description="Topic description")
    document_ids: List[str] = Field(default_factory=list)
    chunk_ids: List[str] = Field(default_factory=list)
    representative_chunks: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(None, description="Topic summary")


class Report(BaseModel):
    id: str = Field(..., description="Report identifier")
    title: str = Field(..., description="Report title")
    created_at: datetime = Field(default_factory=datetime.now)
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    executive_summary: str = Field(..., description="Executive summary")
    topics: List[Topic] = Field(default_factory=list)
    document_count: int = Field(..., description="Total documents processed")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PipelineStatus(BaseModel):
    status: str = Field(..., description="Pipeline status")
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    documents_processed: int = Field(default=0)
    topics_identified: int = Field(default=0)
    error: Optional[str] = Field(None)
    report_id: Optional[str] = Field(None)
    report_url: Optional[str] = Field(None)