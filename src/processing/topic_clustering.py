import logging
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import defaultdict
from openai import OpenAI

import src.core.config as config
from src.core.models import Topic, DocumentChunk
from src.processing.vector_store import VectorStore
from src.processing.thematic_classifier import ThematicClassifier, ThematicPillar

logger = logging.getLogger(__name__)


class TopicClusterer:
    """Identify and cluster topics from document embeddings."""

    def __init__(self,
                 max_topics: int = None,
                 min_topic_size: int = None,
                 api_key: str = None):
        """Initialize topic clusterer."""
        self.max_topics = max_topics or (config.settings or config.init_settings()).max_topics
        self.min_topic_size = min_topic_size or (config.settings or config.init_settings()).min_topic_size
        self.api_key = api_key or (config.settings or config.init_settings()).openai_api_key
        self.client = OpenAI(api_key=self.api_key)
        self.clusters = None
        self.cluster_centers = None

    def find_optimal_clusters(self, embeddings: np.ndarray, min_k: int = 2) -> int:
        """Find optimal number of clusters using silhouette score."""
        max_k = min(self.max_topics, len(embeddings) // self.min_topic_size)

        if max_k < min_k:
            logger.warning(f"Not enough data for clustering. Using k=1")
            return 1

        best_k = min_k
        best_score = -1

        for k in range(min_k, max_k + 1):
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = kmeans.fit_predict(embeddings)

                # Calculate silhouette score
                score = silhouette_score(embeddings, labels)

                logger.info(f"K={k}, silhouette score={score:.3f}")

                if score > best_score:
                    best_score = score
                    best_k = k

            except Exception as e:
                logger.error(f"Error computing clusters for k={k}: {e}")
                continue

        logger.info(f"Optimal number of clusters: {best_k}")
        return best_k

    def cluster_embeddings(self, vector_store: VectorStore) -> Dict[int, List[DocumentChunk]]:
        """Cluster document chunks based on their embeddings."""
        embeddings = vector_store.get_embeddings_matrix()

        if len(embeddings) == 0:
            logger.error("No embeddings available for clustering")
            return {}

        # Find optimal number of clusters
        n_clusters = self.find_optimal_clusters(embeddings)

        # Perform clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.clusters = kmeans.fit_predict(embeddings)
        self.cluster_centers = kmeans.cluster_centers_

        # Group chunks by cluster
        cluster_groups = defaultdict(list)
        chunks = vector_store.get_all_chunks()

        for idx, cluster_id in enumerate(self.clusters):
            if idx < len(chunks):
                cluster_groups[int(cluster_id)].append(chunks[idx])

        # Filter out small clusters
        filtered_groups = {}
        for cluster_id, chunks in cluster_groups.items():
            if len(chunks) >= self.min_topic_size:
                filtered_groups[cluster_id] = chunks
            else:
                logger.info(f"Filtering out cluster {cluster_id} with only {len(chunks)} chunks")

        logger.info(f"Created {len(filtered_groups)} topic clusters")
        return filtered_groups

    def generate_topic_name(self, chunks: List[DocumentChunk], max_chunks: int = 5) -> str:
        """Generate a descriptive name for a topic based on its chunks."""
        # Select representative chunks (closest to cluster center if available)
        sample_chunks = chunks[:max_chunks]

        # Combine chunk texts
        combined_text = "\n\n".join([chunk.content[:500] for chunk in sample_chunks])

        try:
            response = self.client.chat.completions.create(
                model=(config.settings or config.init_settings()).openai_model_chat,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at identifying and naming topics. Generate a concise, descriptive topic name (3-6 words) based on the provided text samples."
                    },
                    {
                        "role": "user",
                        "content": f"Based on these text samples, generate a topic name:\n\n{combined_text}"
                    }
                ],
                max_tokens=50,
                temperature=0.3
            )

            topic_name = response.choices[0].message.content.strip()
            return topic_name

        except Exception as e:
            logger.error(f"Error generating topic name: {e}")
            return "General Topic"

    def generate_topic_description(self, chunks: List[DocumentChunk], max_chunks: int = 10) -> str:
        """Generate a description for a topic based on its chunks."""
        # Select representative chunks
        sample_chunks = chunks[:max_chunks]

        # Combine chunk texts
        combined_text = "\n\n".join([chunk.content[:300] for chunk in sample_chunks])

        try:
            response = self.client.chat.completions.create(
                model=(config.settings or config.init_settings()).openai_model_chat,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing and describing topics. Generate a clear, concise description (2-3 sentences) that captures the main themes and content of the topic."
                    },
                    {
                        "role": "user",
                        "content": f"Based on these text samples, describe the topic:\n\n{combined_text}"
                    }
                ],
                max_tokens=150,
                temperature=0.3
            )

            description = response.choices[0].message.content.strip()
            return description

        except Exception as e:
            logger.error(f"Error generating topic description: {e}")
            return "A collection of related documents and content."

    def get_representative_chunks(self, chunks: List[DocumentChunk],
                                 cluster_id: int, n: int = 5) -> List[str]:
        """Get the most representative chunks for a cluster."""
        if not self.cluster_centers is not None and cluster_id < len(self.cluster_centers):
            # Find chunks closest to cluster center
            center = self.cluster_centers[cluster_id]

            # Calculate distances from center
            distances = []
            for chunk in chunks:
                if chunk.embedding:
                    embedding = np.array(chunk.embedding)
                    distance = np.linalg.norm(embedding - center)
                    distances.append((chunk.id, distance))

            # Sort by distance and get top n
            distances.sort(key=lambda x: x[1])
            representative_ids = [chunk_id for chunk_id, _ in distances[:n]]

            return representative_ids
        else:
            # Fallback: just take first n chunks
            return [chunk.id for chunk in chunks[:n]]

    def create_topics(self, vector_store: VectorStore) -> List[Topic]:
        """Create topics from embeddings.

        If topic_mode is 'thematic', create fixed AI/Customer Journey/Digital Performance topics
        using ThematicClassifier; otherwise, fall back to KMeans clustering.
        """
        settings = config.settings or config.init_settings()
        if settings.topic_mode.lower() == "thematic":
            classifier = ThematicClassifier()
            assignments = classifier.classify_chunks(vector_store)

            topics: List[Topic] = []
            pillar_meta = {
                ThematicPillar.AI: ("topic_ai", "AI"),
                ThematicPillar.CUSTOMER_JOURNEY: ("topic_customer_journey", "Customer Journey"),
                ThematicPillar.DIGITAL_PERFORMANCE: ("topic_digital_performance", "Digital Performance"),
            }

            for pillar, (topic_id, topic_name) in pillar_meta.items():
                chunks = assignments.get(pillar, [])
                if not chunks:
                    continue
                document_ids = list(set(chunk.document_id for chunk in chunks))
                chunk_ids = [chunk.id for chunk in chunks]
                # For thematic mode, take first n chunks as representatives
                representative_chunks = [c.id for c in chunks[:5]]
                description = self.generate_topic_description(chunks)
                topic = Topic(
                    id=topic_id,
                    name=topic_name,
                    description=description,
                    document_ids=document_ids,
                    chunk_ids=chunk_ids,
                    representative_chunks=representative_chunks,
                )
                topics.append(topic)
                logger.info(f"Created thematic topic: {topic_name} with {len(chunks)} chunks")
            return topics

        # Fallback to auto clustering
        cluster_groups = self.cluster_embeddings(vector_store)

        if not cluster_groups:
            logger.warning("No clusters found")
            return []

        topics = []

        for cluster_id, chunks in cluster_groups.items():
            # Get unique document IDs
            document_ids = list(set(chunk.document_id for chunk in chunks))

            # Get chunk IDs
            chunk_ids = [chunk.id for chunk in chunks]

            # Get representative chunks
            representative_chunks = self.get_representative_chunks(chunks, cluster_id)

            # Generate topic name and description
            topic_name = self.generate_topic_name(chunks)
            topic_description = self.generate_topic_description(chunks)

            topic = Topic(
                id=f"topic_{cluster_id}",
                name=topic_name,
                description=topic_description,
                document_ids=document_ids,
                chunk_ids=chunk_ids,
                representative_chunks=representative_chunks
            )

            topics.append(topic)
            logger.info(f"Created topic: {topic_name} with {len(chunks)} chunks from {len(document_ids)} documents")

        return topics

    def refine_topics(self, topics: List[Topic], min_similarity: float = 0.7) -> List[Topic]:
        """Refine topics by merging similar ones."""
        # This is a placeholder for more sophisticated topic refinement
        # Could implement topic merging based on semantic similarity
        return topics
