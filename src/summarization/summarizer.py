import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain.schema import Document as LangchainDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter

import src.core.config as config
from src.core.models import Topic, Document, DocumentChunk
from src.processing.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Summarizer:
    """Generate summaries for topics and documents using LangChain and OpenAI."""

    def __init__(self, api_key: str = None):
        """Initialize the summarizer with OpenAI configuration."""
        active_settings = config.settings or config.init_settings()
        self.settings = active_settings
        self.api_key = api_key or active_settings.openai_api_key
        # Lazy-init LLMs to keep tests lightweight
        self.chat_llm = None
        self.summary_llm = None

    def _ensure_llms(self) -> None:
        """Lazily initialize LLM clients when first needed."""
        if self.chat_llm is None:
            self.chat_llm = ChatOpenAI(
                api_key=self.api_key,
                model=self.settings.openai_model_chat,
                temperature=0.3,
                max_tokens=1000
            )
        if self.summary_llm is None:
            self.summary_llm = ChatOpenAI(
                api_key=self.api_key,
                model=self.settings.openai_model_summarization,
                temperature=0.2,
                max_tokens=2000
            )

    def summarize_topic(self, topic: Topic, vector_store: VectorStore) -> str:
        """Generate a comprehensive summary for a topic."""
        self._ensure_llms()
        # Get representative chunks
        representative_texts = []

        for chunk_id in topic.representative_chunks[:10]:  # Limit to top 10 chunks
            chunk = vector_store.search_by_chunk_id(chunk_id)
            if chunk:
                representative_texts.append(chunk.content)

        if not representative_texts:
            logger.warning(f"No representative texts found for topic {topic.name}")
            return "No content available for summarization."

        # Create LangChain documents
        docs = [LangchainDocument(page_content=text) for text in representative_texts]

        # Define the summarization prompt
        prompt_template = """You are an expert business analyst creating a summary for a specific topic.

Topic: {topic_name}
Description: {topic_description}

Based on the following content, create a comprehensive business summary that:
1. Identifies key points and insights
2. Highlights important trends or patterns
3. Notes any critical issues or opportunities
4. Provides actionable takeaways

Content:
{text}

BUSINESS SUMMARY:"""

        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["text", "topic_name", "topic_description"]
        )

        # Use map-reduce chain for longer content
        if len(representative_texts) > 3:
            chain = load_summarize_chain(
                self.summary_llm,
                chain_type="map_reduce",
                map_prompt=prompt,
                combine_prompt=prompt,
                verbose=False
            )
        else:
            chain = load_summarize_chain(
                self.summary_llm,
                chain_type="stuff",
                prompt=prompt,
                verbose=False
            )

        try:
            summary = chain.invoke({
                "input_documents": docs,
                "topic_name": topic.name,
                "topic_description": topic.description
            })

            # Extract the summary text from the response
            if isinstance(summary, dict) and 'output_text' in summary:
                summary_text = summary['output_text']
            else:
                summary_text = str(summary)

            logger.info(f"Generated summary for topic: {topic.name}")
            return summary_text

        except Exception as e:
            logger.error(f"Error summarizing topic {topic.name}: {e}")
            return f"Error generating summary for {topic.name}"

    def summarize_pillar(self,
                         pillar_name: str,
                         chunks: List[DocumentChunk],
                         document_info_by_id: Dict[str, Dict[str, str]]) -> str:
        """Summarize a fixed pillar with ICP-aware structure (returns Markdown)."""
        self._ensure_llms()
        # Prepare text samples
        sample_texts = [c.content[:600] for c in chunks[:10] if c.content]
        docs_for_citations = []
        for c in chunks[:20]:
            doc_info = document_info_by_id.get(c.metadata.get('document_id', c.document_id), {})
            title = doc_info.get('title') or c.metadata.get('document_name')
            url = doc_info.get('url') or c.metadata.get('web_view_link')
            if title or url:
                docs_for_citations.append(f"{title or 'Document'}{f' ({url})' if url else ''}")
        docs_for_citations = list(dict.fromkeys(docs_for_citations))[:8]

        instructions = (
            "You are writing for the following target audience (ICP):\n"
            f"{self.settings.audience_profile}\n\n"
            "Scope: ONLY include insights relevant to this pillar; ignore unrelated content.\n"
            "Tone: empathetic, expert, confidence-building, business-to-people (B2P).\n"
            "Output Markdown with EXACT sections and nothing else."
        )

        template = PromptTemplate(
            template=(
                "{instructions}\n\n"
                "Pillar: {pillar}\n\n"
                "Text samples (representative excerpts):\n{samples}\n\n"
                "Potential sources to cite (title and/or URL):\n- " + "\n- ".join(docs_for_citations) + "\n\n"
                "Return Markdown with these sections:\n\n"
                "1. Key Findings for {pillar}\n"
                "- Five concise bullets synthesizing common ideas. After each bullet, append sources as (Source: Title or URL).\n\n"
                "2. Trends & Patterns\n"
                "- 3-5 bullets on directional movements.\n\n"
                "3. Risks & Opportunities\n"
                "- 3-5 bullets; explicitly flag confidence/quality risks.\n\n"
                "4. Our Take (Conclusion + Actionable Takeaways)\n"
                "- One short paragraph with our agency POV for this ICP, followed by 3-5 actionable recommendations.\n"
            ),
            input_variables=["instructions", "pillar", "samples"],
        )

        try:
            response = self.summary_llm.invoke(
                template.format(
                    instructions=instructions,
                    pillar=pillar_name,
                    samples="\n\n".join(sample_texts) or "",
                )
            )
            return getattr(response, 'content', str(response))
        except Exception as e:
            logger.error(f"Error summarizing pillar {pillar_name}: {e}")
            return f"## {pillar_name}\n\nError generating pillar summary."

    def generate_executive_summary(self, topics: List[Topic],
                                  documents: List[Document],
                                  report_period: str = "this period") -> str:
        """Generate an executive summary covering all topics.

        Note: Will be updated to synthesize across the three fixed pillars for
        the specified ICP and include a cross-pillar recommendation set.
        """
        self._ensure_llms()
        # Prepare topic summaries
        topic_info = []
        for topic in topics[:10]:  # Limit to top 10 topics
            if topic.summary:
                topic_info.append(f"**{topic.name}**: {topic.summary[:300]}...")

        topics_text = "\n\n".join(topic_info)

        # Create the executive summary prompt
        prompt = PromptTemplate(
            template="""You are a senior business analyst creating an executive summary for C-level executives.

Reporting Period: {period}
Number of Documents Analyzed: {doc_count}
Number of Topics Identified: {topic_count}

Topic Summaries:
{topics_text}

Create an executive summary that:
1. Provides a high-level overview of the key findings
2. Identifies the most critical business insights
3. Highlights strategic opportunities and risks
4. Suggests priority areas for attention
5. Concludes with 3-5 actionable recommendations

Keep the summary concise but comprehensive (maximum {max_length} words).

EXECUTIVE SUMMARY:""",
            input_variables=["period", "doc_count", "topic_count", "topics_text", "max_length"]
        )

        try:
            response = self.summary_llm.invoke(
                prompt.format(
                    period=report_period,
                    doc_count=len(documents),
                    topic_count=len(topics),
                    topics_text=topics_text,
                    max_length=self.settings.executive_summary_length // 5  # Approximate word count
                )
            )

            if hasattr(response, 'content'):
                summary = response.content
            else:
                summary = str(response)

            logger.info("Generated executive summary")
            return summary

        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return "Error generating executive summary."

    def summarize_document(self, document: Document, max_length: int = None) -> str:
        """Generate a summary for a single document."""
        self._ensure_llms()
        max_length = max_length or self.settings.max_summary_length

        if not document.content:
            return "No content available for summarization."

        # Truncate if too long
        content = document.content[:10000]  # Limit input size

        prompt = PromptTemplate(
            template="""Summarize the following document concisely:

Document: {title}
Type: {doc_type}

Content:
{content}

Provide a clear, business-focused summary (maximum {max_length} characters):

SUMMARY:""",
            input_variables=["title", "doc_type", "content", "max_length"]
        )

        try:
            response = self.chat_llm.invoke(
                prompt.format(
                    title=document.name,
                    doc_type=document.type,
                    content=content,
                    max_length=max_length
                )
            )

            if hasattr(response, 'content'):
                summary = response.content
            else:
                summary = str(response)

            # Ensure summary is within length limit
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."

            return summary

        except Exception as e:
            logger.error(f"Error summarizing document {document.name}: {e}")
            return "Error generating document summary."

    def generate_topic_insights(self, topic: Topic, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """Generate detailed insights for a topic."""
        self._ensure_llms()
        # Combine chunk contents
        combined_text = "\n\n".join([chunk.content[:500] for chunk in chunks[:10]])

        prompt = PromptTemplate(
            template="""Analyze the following content and provide structured business insights:

Topic: {topic_name}

Content:
{content}

Provide insights in the following format:
1. KEY FINDINGS: (2-3 bullet points)
2. TRENDS: (identify any patterns or trends)
3. RISKS: (potential issues or concerns)
4. OPPORTUNITIES: (potential benefits or advantages)
5. RECOMMENDATIONS: (1-2 actionable items)

INSIGHTS:""",
            input_variables=["topic_name", "content"]
        )

        try:
            response = self.chat_llm.invoke(
                prompt.format(
                    topic_name=topic.name,
                    content=combined_text
                )
            )

            if hasattr(response, 'content'):
                insights_text = response.content
            else:
                insights_text = str(response)

            # Parse the insights (simplified - could be enhanced)
            insights = {
                "raw_insights": insights_text,
                "topic_name": topic.name,
                "document_count": len(set(chunk.document_id for chunk in chunks)),
                "chunk_count": len(chunks)
            }

            return insights

        except Exception as e:
            logger.error(f"Error generating insights for topic {topic.name}: {e}")
            return {
                "raw_insights": "Error generating insights",
                "topic_name": topic.name,
                "document_count": 0,
                "chunk_count": 0
            }
