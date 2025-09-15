import logging
from typing import List, Dict, Any
import numpy as np
from openai import OpenAI

import src.core.config as config
from src.core.models import Document, DocumentChunk

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for document chunks using OpenAI."""

    def __init__(self, api_key: str = None, model: str = None):
        """Initialize the embedding generator."""
        active_settings = config.settings or config.init_settings()
        self.api_key = api_key or active_settings.openai_api_key
        self.model = model or active_settings.openai_model_embedding
        self.client = OpenAI(api_key=self.api_key)

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embedding = response.data[0].embedding
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch."""
        embeddings = []

        # OpenAI has a limit on batch size, process in chunks
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)

                logger.info(f"Generated embeddings for batch {i//batch_size + 1}")

            except Exception as e:
                logger.error(f"Error generating batch embeddings: {e}")
                # Fill with empty embeddings for failed batch
                embeddings.extend([[] for _ in batch])

        return embeddings

    def process_documents(self, documents: List[Document]) -> List[DocumentChunk]:
        """Process documents and generate embeddings for their chunks."""
        all_chunks = []

        for doc in documents:
            chunks_text = doc.metadata.get('chunks', [])

            if not chunks_text:
                logger.warning(f"No chunks found for document {doc.name}")
                continue

            # Generate embeddings for this document's chunks
            chunk_embeddings = self.generate_embeddings_batch(chunks_text)

            # Create DocumentChunk objects
            for idx, (chunk_id, text, embedding) in enumerate(
                zip(doc.chunk_ids, chunks_text, chunk_embeddings)
            ):
                chunk = DocumentChunk(
                    id=chunk_id,
                    document_id=doc.id,
                    content=text,
                    embedding=embedding,
                    metadata={
                        'document_name': doc.name,
                        'document_type': doc.type,
                        'chunk_index': idx,
                        'total_chunks': len(chunks_text)
                    }
                )
                all_chunks.append(chunk)

            logger.info(f"Processed {len(chunks_text)} chunks for document {doc.name}")

        logger.info(f"Generated embeddings for {len(all_chunks)} total chunks")
        return all_chunks

    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        if not embedding1 or not embedding2:
            return 0.0

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
