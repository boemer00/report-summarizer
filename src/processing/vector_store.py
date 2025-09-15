import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import faiss
import pickle
from pathlib import Path

from src.core.models import DocumentChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS-based vector store for document embeddings."""
    
    def __init__(self, dimension: int = 1536):
        """Initialize vector store with specified embedding dimension."""
        self.dimension = dimension
        self.index = None
        self.chunks: List[DocumentChunk] = []
        self.chunk_map: Dict[str, int] = {}  # Maps chunk_id to index position
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize FAISS index."""
        # Using L2 distance for simplicity, can switch to cosine similarity
        self.index = faiss.IndexFlatL2(self.dimension)
        logger.info(f"Initialized FAISS index with dimension {self.dimension}")
    
    def add_chunks(self, chunks: List[DocumentChunk]):
        """Add document chunks with embeddings to the vector store."""
        valid_chunks = []
        embeddings = []
        
        for chunk in chunks:
            if chunk.embedding and len(chunk.embedding) == self.dimension:
                valid_chunks.append(chunk)
                embeddings.append(chunk.embedding)
            else:
                logger.warning(f"Skipping chunk {chunk.id} with invalid embedding")
        
        if not valid_chunks:
            logger.warning("No valid chunks to add to vector store")
            return
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # Add to index
        start_idx = len(self.chunks)
        self.index.add(embeddings_array)
        
        # Update internal storage
        for i, chunk in enumerate(valid_chunks):
            self.chunks.append(chunk)
            self.chunk_map[chunk.id] = start_idx + i
        
        logger.info(f"Added {len(valid_chunks)} chunks to vector store")
    
    def search(self, query_embedding: List[float], k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """Search for similar chunks using query embedding."""
        if not query_embedding or len(query_embedding) != self.dimension:
            logger.error("Invalid query embedding")
            return []
        
        if self.index.ntotal == 0:
            logger.warning("Vector store is empty")
            return []
        
        # Convert to numpy array
        query_array = np.array([query_embedding], dtype=np.float32)
        
        # Search
        distances, indices = self.index.search(query_array, min(k, self.index.ntotal))
        
        # Prepare results
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                # Convert L2 distance to similarity score (inverse)
                similarity = 1.0 / (1.0 + float(distance))
                results.append((chunk, similarity))
        
        return results
    
    def search_by_chunk_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Retrieve a specific chunk by its ID."""
        idx = self.chunk_map.get(chunk_id)
        if idx is not None and idx < len(self.chunks):
            return self.chunks[idx]
        return None
    
    def get_chunks_by_document(self, document_id: str) -> List[DocumentChunk]:
        """Get all chunks belonging to a specific document."""
        return [chunk for chunk in self.chunks if chunk.document_id == document_id]
    
    def get_all_chunks(self) -> List[DocumentChunk]:
        """Get all chunks in the vector store."""
        return self.chunks.copy()
    
    def get_embeddings_matrix(self) -> np.ndarray:
        """Get all embeddings as a numpy matrix."""
        if not self.chunks:
            return np.array([])
        
        embeddings = [chunk.embedding for chunk in self.chunks if chunk.embedding]
        return np.array(embeddings, dtype=np.float32)
    
    def save(self, path: Path):
        """Save vector store to disk."""
        try:
            # Save FAISS index
            faiss.write_index(self.index, str(path / "faiss.index"))
            
            # Save chunks and metadata
            with open(path / "chunks.pkl", "wb") as f:
                pickle.dump({
                    'chunks': self.chunks,
                    'chunk_map': self.chunk_map,
                    'dimension': self.dimension
                }, f)
            
            logger.info(f"Vector store saved to {path}")
            
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")
            raise
    
    def load(self, path: Path):
        """Load vector store from disk."""
        try:
            # Load FAISS index
            self.index = faiss.read_index(str(path / "faiss.index"))
            
            # Load chunks and metadata
            with open(path / "chunks.pkl", "rb") as f:
                data = pickle.load(f)
                self.chunks = data['chunks']
                self.chunk_map = data['chunk_map']
                self.dimension = data['dimension']
            
            logger.info(f"Vector store loaded from {path}")
            
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            raise
    
    def clear(self):
        """Clear the vector store."""
        self._initialize_index()
        self.chunks.clear()
        self.chunk_map.clear()
        logger.info("Vector store cleared")
    
    def size(self) -> int:
        """Get the number of chunks in the store."""
        return len(self.chunks)
    
    def find_similar_chunks(self, chunk_id: str, k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """Find chunks similar to a given chunk."""
        chunk = self.search_by_chunk_id(chunk_id)
        if not chunk or not chunk.embedding:
            return []
        
        # Search for similar chunks (k+1 because it will include itself)
        results = self.search(chunk.embedding, k + 1)
        
        # Filter out the query chunk itself
        return [(c, score) for c, score in results if c.id != chunk_id][:k]