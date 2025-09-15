import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import uuid

import src.core.config as config
from src.core.models import Report, PipelineStatus
from src.extractors.drive_client import DriveClient
from src.extractors.docs_client import DocsClient
from src.extractors.document_parser import DocumentParser
from src.processing.embeddings import EmbeddingGenerator
from src.processing.vector_store import VectorStore
from src.processing.topic_clustering import TopicClusterer
from src.processing.thematic_classifier import ThematicPillar
from src.summarization.summarizer import Summarizer
from src.summarization.report_generator import ReportGenerator
from src.summarization.pillar_synthesis import PillarSynopsisGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Pipeline:
    """Main pipeline for document processing and report generation."""

    def __init__(self):
        """Initialize the pipeline with all components."""
        # Initialize settings
        config.init_settings()

        # Initialize components
        self.drive_client = DriveClient()
        self.docs_client = DocsClient()
        self.document_parser = DocumentParser(
            chunk_size=config.settings.chunk_size,
            chunk_overlap=config.settings.chunk_overlap
        )
        self.embedding_generator = EmbeddingGenerator()
        self.vector_store = VectorStore()
        self.topic_clusterer = TopicClusterer()
        self.summarizer = Summarizer()
        self.report_generator = ReportGenerator()
        self.pillar_synopsis = PillarSynopsisGenerator()

        # Pipeline state
        self.status = PipelineStatus(status="idle")
        self.current_report = None

    def run(self,
            folder_id: Optional[str] = None,
            output_folder_id: Optional[str] = None,
            save_to_drive: bool = True,
            use_specific_sources: bool = True) -> Dict[str, Any]:
        """Run the complete pipeline.

        Args:
            folder_id: Optional Drive folder ID (uses default if None)
            output_folder_id: Optional output folder ID
            save_to_drive: Whether to save report to Drive
            use_specific_sources: If True, uses PDF folder and Google Doc; if False, uses regular folder
        """
        try:
            self.status = PipelineStatus(
                status="running",
                started_at=datetime.now()
            )

            logger.info("Starting document summarization pipeline")

            documents = []

            if use_specific_sources:
                # Step 1a: Extract PDF reports from specific Drive folder
                logger.info("Step 1a: Extracting PDF reports from Google Drive")
                if config.settings.pdf_reports_folder_id:
                    pdf_documents = self.drive_client.extract_pdf_reports(config.settings.pdf_reports_folder_id)
                    documents.extend(pdf_documents)
                    logger.info(f"Extracted {len(pdf_documents)} PDF reports")

                # Step 1b: Extract URLs from Google Doc
                logger.info("Step 1b: Extracting URLs from Google Doc")
                if config.settings.google_doc_id:
                    url_documents = self.docs_client.create_url_documents(config.settings.google_doc_id)
                    documents.extend(url_documents)
                    logger.info(f"Extracted {len(url_documents)} URLs from Google Doc")
            else:
                # Original behavior: extract all documents from a folder
                logger.info("Step 1: Extracting documents from Google Drive")
                documents = self.drive_client.extract_documents(folder_id)

            if not documents:
                raise ValueError("No documents found from the specified sources")

            self.status.documents_processed = len(documents)
            logger.info(f"Total documents to process: {len(documents)}")

            # Step 2: Parse and chunk documents
            logger.info("Step 2: Parsing and chunking documents")
            parsed_documents = self.document_parser.process_documents(documents)

            # Step 3: Generate embeddings
            logger.info("Step 3: Generating embeddings")
            chunks = self.embedding_generator.process_documents(parsed_documents)

            # Step 4: Build vector store
            logger.info("Step 4: Building vector store")
            self.vector_store.clear()
            # Adjust vector store dimension dynamically to embedding size
            first_valid = next((c for c in chunks if c.embedding and len(c.embedding) > 0), None)
            if first_valid and len(first_valid.embedding) != self.vector_store.dimension:
                self.vector_store = VectorStore(dimension=len(first_valid.embedding))
                logger.info(f"Reinitialized vector store to dimension {len(first_valid.embedding)}")
            self.vector_store.add_chunks(chunks)

            # Step 5: Identify topics (thematic or auto)
            logger.info("Step 5: Identifying topics (thematic or auto)")
            topics = self.topic_clusterer.create_topics(self.vector_store)
            self.status.topics_identified = len(topics)

            # Step 6: Generate summaries (pillar-aware if using thematic mode)
            logger.info("Step 6: Generating summaries")
            ai_md = cj_md = dp_md = None
            topic_names = {t.id: t.name for t in topics}
            # Build doc info mapping for citations
            doc_info = {}
            for doc in parsed_documents:
                url = doc.source if doc.type.value == 'url' else doc.metadata.get('web_view_link')
                doc_info[doc.id] = {"title": doc.name, "url": url}

            if any(t.id.startswith("topic_") and t.id in ("topic_ai", "topic_customer_journey", "topic_digital_performance") for t in topics):
                # Collect chunks by topic id
                chunks_by_id = {c.id: c for c in self.vector_store.get_all_chunks()}
                for t in topics:
                    t_chunks = [chunks_by_id[cid] for cid in t.chunk_ids if cid in chunks_by_id]
                    if (config.settings or config.init_settings()).synopsis_enable:
                        # New synopsis path
                        if t.id == "topic_ai":
                            ai_md = self.pillar_synopsis.generate_synopsis(
                                pillar_name="AI",
                                chunks=t_chunks,
                                doc_info_by_id=doc_info,
                                max_source_citations=(config.settings or config.init_settings()).synopsis_max_citations,
                                paragraphs=(config.settings or config.init_settings()).synopsis_paragraphs,
                            )
                        elif t.id == "topic_customer_journey":
                            cj_md = self.pillar_synopsis.generate_synopsis(
                                pillar_name="Customer Journey",
                                chunks=t_chunks,
                                doc_info_by_id=doc_info,
                                max_source_citations=(config.settings or config.init_settings()).synopsis_max_citations,
                                paragraphs=(config.settings or config.init_settings()).synopsis_paragraphs,
                            )
                        elif t.id == "topic_digital_performance":
                            dp_md = self.pillar_synopsis.generate_synopsis(
                                pillar_name="Digital Performance",
                                chunks=t_chunks,
                                doc_info_by_id=doc_info,
                                max_source_citations=(config.settings or config.init_settings()).synopsis_max_citations,
                                paragraphs=(config.settings or config.init_settings()).synopsis_paragraphs,
                            )
                    else:
                        # Legacy pillar summarizer path
                        if t.id == "topic_ai":
                            ai_md = self.summarizer.summarize_pillar("AI", t_chunks, doc_info)
                        elif t.id == "topic_customer_journey":
                            cj_md = self.summarizer.summarize_pillar("Customer Journey", t_chunks, doc_info)
                        elif t.id == "topic_digital_performance":
                            dp_md = self.summarizer.summarize_pillar("Digital Performance", t_chunks, doc_info)
            else:
                for topic in topics:
                    topic.summary = self.summarizer.summarize_topic(topic, self.vector_store)

            # Step 7: Generate executive summary
            logger.info("Step 7: Generating executive summary")
            period_end = datetime.now()
            period_start = period_end - timedelta(days=30)  # Last 30 days

            executive_summary = self.summarizer.generate_executive_summary(
                topics=topics,
                documents=parsed_documents,
                report_period=f"{period_start.strftime('%B %Y')}"
            )

            # Step 8: Create report
            logger.info("Step 8: Creating report")
            report = Report(
                id=str(uuid.uuid4()),
                title=config.settings.report_title,
                period_start=period_start,
                period_end=period_end,
                executive_summary=executive_summary,
                topics=topics,
                document_count=len(documents)
            )

            # Step 9: Generate HTML report
            logger.info("Step 9: Generating HTML report")
            if ai_md or cj_md or dp_md:
                final_conclusion_md = "In summary, brands should prioritize confidence-building across AI, Customer Journey, and Digital Performance in the coming period."
                html_content = self.report_generator.render_thematic_report(
                    report=report,
                    ai_markdown=ai_md or "",
                    customer_journey_markdown=cj_md or "",
                    digital_performance_markdown=dp_md or "",
                    final_conclusion_md=final_conclusion_md,
                )
            else:
                html_content = self.report_generator.generate_report(
                    report=report,
                    topics=topics,
                    documents=parsed_documents
                )

            # Step 10: Save report
            logger.info("Step 10: Saving report")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"report_{timestamp}.html"

            # Save locally
            local_path = Path("reports") / report_filename
            saved_path = self.report_generator.save_report(html_content, local_path)
            # Generate PDF if enabled
            pdf_path = None
            pdf_url = None
            try:
                if (config.settings or config.init_settings()).pdf_enabled:
                    pdf_filename = report_filename.replace('.html', '.pdf')
                    pdf_path = Path("reports") / pdf_filename
                    self.report_generator.save_report_pdf(saved_path, pdf_path)
            except Exception as e:
                logger.error(f"Failed to generate PDF: {e}")

            # Save to Google Drive if requested
            report_url = None
            if save_to_drive:
                try:
                    report_url = self.drive_client.upload_report(
                        report_path=saved_path,
                        report_name=f"{config.settings.report_title} - {timestamp}",
                        folder_id=output_folder_id
                    )
                    logger.info(f"Report uploaded to Google Drive: {report_url}")
                    if pdf_path:
                        try:
                            pdf_url = self.drive_client.upload_file(
                                path=pdf_path,
                                name=f"{config.settings.report_title} - {timestamp}.pdf",
                                mime_type='application/pdf',
                                folder_id=output_folder_id
                            )
                            logger.info(f"PDF uploaded to Google Drive: {pdf_url}")
                        except Exception as e:
                            logger.error(f"Failed to upload PDF to Drive: {e}")
                except Exception as e:
                    logger.error(f"Failed to upload report to Drive: {e}")

            # Update status
            self.status.status = "completed"
            self.status.completed_at = datetime.now()
            self.status.report_id = report.id
            self.status.report_url = report_url
            self.current_report = report

            logger.info("Pipeline completed successfully")

            return {
                "success": True,
                "report_id": report.id,
                "report_path": str(saved_path),
                "report_url": report_url,
                "report_pdf_path": str(pdf_path) if pdf_path else None,
                "report_pdf_url": pdf_url,
                "documents_processed": len(documents),
                "topics_identified": len(topics),
                "execution_time": (self.status.completed_at - self.status.started_at).total_seconds()
            }

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.status.status = "failed"
            self.status.error = str(e)
            self.status.completed_at = datetime.now()

            return {
                "success": False,
                "error": str(e),
                "documents_processed": self.status.documents_processed,
                "topics_identified": self.status.topics_identified
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current pipeline status."""
        return {
            "status": self.status.status,
            "started_at": self.status.started_at.isoformat() if self.status.started_at else None,
            "completed_at": self.status.completed_at.isoformat() if self.status.completed_at else None,
            "documents_processed": self.status.documents_processed,
            "topics_identified": self.status.topics_identified,
            "error": self.status.error,
            "report_id": self.status.report_id,
            "report_url": self.status.report_url
        }

    def get_last_report(self) -> Optional[Report]:
        """Get the last generated report."""
        return self.current_report

    def clear_cache(self):
        """Clear the vector store cache."""
        self.vector_store.clear()
        logger.info("Vector store cache cleared")


# Singleton instance
pipeline_instance = None


def get_pipeline() -> Pipeline:
    """Get or create the pipeline singleton instance."""
    global pipeline_instance
    if pipeline_instance is None:
        pipeline_instance = Pipeline()
    return pipeline_instance


def run_pipeline(**kwargs) -> Dict[str, Any]:
    """Convenience function to run the pipeline."""
    pipeline = get_pipeline()
    return pipeline.run(**kwargs)
