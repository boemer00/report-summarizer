import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import markdown
from jinja2 import Template
import pdfkit

import src.core.config as config
from src.core.models import Report, Topic, Document

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate formatted business intelligence reports."""

    def __init__(self):
        """Initialize the report generator."""
        self.settings = config.settings or config.init_settings()
        self.report_template = self._create_report_template()

    def _create_report_template(self) -> Template:
        """Create the HTML report template."""
        template_str = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 600;
        }
        .header .subtitle {
            margin-top: 10px;
            opacity: 0.9;
            font-size: 1.2em;
        }
        .metadata {
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.3);
        }
        .metadata-item {
            text-align: center;
        }
        .metadata-value {
            font-size: 2em;
            font-weight: bold;
            display: block;
        }
        .metadata-label {
            opacity: 0.8;
            font-size: 0.9em;
        }
        .section {
            background: white;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .section h2 {
            color: #667eea;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .executive-summary {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-left: 4px solid #667eea;
            padding: 25px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .topic {
            background: #f8f9fa;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            border-left: 3px solid #764ba2;
        }
        .topic h3 {
            color: #764ba2;
            margin-top: 0;
        }
        .topic-metadata {
            display: flex;
            gap: 20px;
            margin: 10px 0;
            font-size: 0.9em;
            color: #666;
        }
        .topic-description {
            font-style: italic;
            color: #666;
            margin: 10px 0;
        }
        .topic-summary {
            margin-top: 15px;
            line-height: 1.8;
        }
        .documents-list {
            margin-top: 20px;
            padding: 15px;
            background: #f0f0f0;
            border-radius: 5px;
        }
        .document-item {
            padding: 8px 0;
            border-bottom: 1px solid #ddd;
        }
        .document-item:last-child {
            border-bottom: none;
        }
        .footer {
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 0.9em;
            border-top: 2px solid #f0f0f0;
            margin-top: 50px;
        }
        .timestamp {
            color: #999;
            font-size: 0.8em;
        }
        @media print {
            body {
                background-color: white;
            }
            .section {
                box-shadow: none;
                border: 1px solid #ddd;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ title }}</h1>
        <div class="subtitle">{{ period_start }} - {{ period_end }}</div>
        <div class="metadata">
            <div class="metadata-item">
                <span class="metadata-value">{{ document_count }}</span>
                <span class="metadata-label">Documents Analyzed</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-value">{{ topic_count }}</span>
                <span class="metadata-label">Topics Identified</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-value">{{ created_date }}</span>
                <span class="metadata-label">Report Date</span>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Executive Summary</h2>
        <div class="executive-summary">
            {{ executive_summary | safe }}
        </div>
    </div>

    <div class="section">
        <h2>Topics Analysis</h2>
        {% for topic in topics %}
        <div class="topic">
            <h3>{{ topic.name }}</h3>
            <div class="topic-metadata">
                <span>📄 {{ topic.document_count }} documents</span>
                <span>📊 {{ topic.chunk_count }} text segments</span>
            </div>
            <div class="topic-description">{{ topic.description }}</div>
            <div class="topic-summary">
                {{ topic.summary | safe }}
            </div>
            {% if topic.documents %}
            <details class="documents-list">
                <summary>Related Documents</summary>
                {% for doc in topic.documents %}
                <div class="document-item">
                    • {{ doc }}
                </div>
                {% endfor %}
            </details>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <div class="footer">
        <p>Generated on {{ generated_timestamp }}</p>
        <p>{{ report_title }} - Automated Business Intelligence Report</p>
    </div>
</body>
</html>"""

        return Template(template_str)

    def generate_report(self,
                       report: Report,
                       topics: List[Topic],
                       documents: List[Document]) -> str:
        """Generate an HTML report from the analysis results."""
        # Prepare topic data with additional metadata
        topic_data = []
        doc_map = {doc.id: doc.name for doc in documents}

        for topic in topics:
            topic_info = {
                'name': topic.name,
                'description': topic.description,
                'summary': markdown.markdown(topic.summary) if topic.summary else "No summary available",
                'document_count': len(topic.document_ids),
                'chunk_count': len(topic.chunk_ids),
                'documents': [doc_map.get(doc_id, doc_id) for doc_id in topic.document_ids[:5]]  # Show first 5
            }
            topic_data.append(topic_info)

        # Render the template
        html_content = self.report_template.render(
            title=report.title,
            period_start=report.period_start.strftime("%B %d, %Y"),
            period_end=report.period_end.strftime("%B %d, %Y"),
            document_count=report.document_count,
            topic_count=len(topics),
            created_date=report.created_at.strftime("%B %d, %Y"),
            executive_summary=markdown.markdown(report.executive_summary),
            topics=topic_data,
            generated_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            report_title=self.settings.report_title
        )

        return html_content

    def render_thematic_report(self,
                               report: Report,
                               ai_markdown: str,
                               customer_journey_markdown: str,
                               digital_performance_markdown: str,
                               final_conclusion_md: str) -> str:
        """Render a fixed-structure report for the three pillars into HTML."""
        sections_template = Template(
            """
<div class="section">
  <h2>AI</h2>
  <div class="topic-summary">{{ ai_html|safe }}</div>
</div>
<div class="section">
  <h2>Customer Journey</h2>
  <div class="topic-summary">{{ cj_html|safe }}</div>
</div>
<div class="section">
  <h2>Digital Performance</h2>
  <div class="topic-summary">{{ dp_html|safe }}</div>
</div>
<div class="section">
  <h2>Final Conclusion</h2>
  <div class="topic-summary">{{ conclusion_html|safe }}</div>
</div>
"""
        )

        ai_html = markdown.markdown(ai_markdown or "")
        cj_html = markdown.markdown(customer_journey_markdown or "")
        dp_html = markdown.markdown(digital_performance_markdown or "")
        conclusion_html = markdown.markdown(final_conclusion_md or "")

        body_html = sections_template.render(
            ai_html=ai_html,
            cj_html=cj_html,
            dp_html=dp_html,
            conclusion_html=conclusion_html,
        )

        # Wrap into the existing layout by using the standard generator
        topic_stub = []  # not used here; we inject body directly
        html_content = self.report_template.render(
            title=report.title,
            period_start=report.period_start.strftime("%B %d, %Y"),
            period_end=report.period_end.strftime("%B %d, %Y"),
            document_count=report.document_count,
            topic_count=len(report.topics),
            created_date=report.created_at.strftime("%B %d, %Y"),
            executive_summary=markdown.markdown(report.executive_summary),
            topics=topic_stub,
            generated_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            report_title=self.settings.report_title
        )

        # Insert the sections after executive summary section
        insertion_marker = "</div>\n\n    <div class=\"section\">\n        <h2>Topics Analysis</h2>"
        if insertion_marker in html_content:
            parts = html_content.split(insertion_marker)
            html_content = parts[0] + insertion_marker + "\n" + body_html + "\n" + (parts[1] if len(parts) > 1 else "")

        return html_content

    def save_report(self, html_content: str, output_path: Path) -> Path:
        """Save the HTML report to a file."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding='utf-8')
            logger.info(f"Report saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            raise

    def save_report_pdf(self, html_path: Path, output_pdf_path: Path) -> Path:
        """Convert an HTML file to PDF using pdfkit/wkhtmltopdf."""
        try:
            options = {
                'page-size': self.settings.pdf_page_size,
                'orientation': self.settings.pdf_orientation,
                'margin-top': f"{self.settings.pdf_margins_mm}mm",
                'margin-right': f"{self.settings.pdf_margins_mm}mm",
                'margin-bottom': f"{self.settings.pdf_margins_mm}mm",
                'margin-left': f"{self.settings.pdf_margins_mm}mm",
                'encoding': "UTF-8",
                'enable-local-file-access': None,
            }
            config_obj = None
            if self.settings.wkhtmltopdf_path:
                config_obj = pdfkit.configuration(wkhtmltopdf=self.settings.wkhtmltopdf_path)

            output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdfkit.from_file(str(html_path), str(output_pdf_path), options=options, configuration=config_obj)
            logger.info(f"PDF report saved to {output_pdf_path}")
            return output_pdf_path
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise

    def generate_markdown_report(self,
                                report: Report,
                                topics: List[Topic],
                                documents: List[Document]) -> str:
        """Generate a Markdown version of the report."""
        doc_map = {doc.id: doc.name for doc in documents}

        md_lines = [
            f"# {report.title}",
            f"*Report Period: {report.period_start.strftime('%B %d, %Y')} - {report.period_end.strftime('%B %d, %Y')}*",
            "",
            "---",
            "",
            "## Summary Statistics",
            f"- **Documents Analyzed:** {report.document_count}",
            f"- **Topics Identified:** {len(topics)}",
            f"- **Report Generated:** {report.created_at.strftime('%B %d, %Y')}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            report.executive_summary,
            "",
            "---",
            "",
            "## Topics Analysis",
            ""
        ]

        for i, topic in enumerate(topics, 1):
            md_lines.extend([
                f"### {i}. {topic.name}",
                "",
                f"*{topic.description}*",
                "",
                f"**Statistics:**",
                f"- Documents: {len(topic.document_ids)}",
                f"- Text Segments: {len(topic.chunk_ids)}",
                "",
                "**Summary:**",
                "",
                topic.summary or "No summary available",
                "",
                "**Related Documents:**",
                ""
            ])

            for doc_id in topic.document_ids[:5]:
                doc_name = doc_map.get(doc_id, doc_id)
                md_lines.append(f"- {doc_name}")

            if len(topic.document_ids) > 5:
                md_lines.append(f"- ... and {len(topic.document_ids) - 5} more")

            md_lines.extend(["", "---", ""])

        md_lines.extend([
            "",
            f"*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        return "\n".join(md_lines)

    def create_summary_json(self,
                           report: Report,
                           topics: List[Topic],
                           documents: List[Document]) -> Dict[str, Any]:
        """Create a JSON summary of the report for API responses."""
        return {
            "report_id": report.id,
            "title": report.title,
            "created_at": report.created_at.isoformat(),
            "period": {
                "start": report.period_start.isoformat(),
                "end": report.period_end.isoformat()
            },
            "statistics": {
                "documents_processed": report.document_count,
                "topics_identified": len(topics)
            },
            "executive_summary": report.executive_summary,
            "topics": [
                {
                    "id": topic.id,
                    "name": topic.name,
                    "description": topic.description,
                    "summary": topic.summary,
                    "document_count": len(topic.document_ids),
                    "chunk_count": len(topic.chunk_ids)
                }
                for topic in topics
            ],
            "metadata": report.metadata
        }
