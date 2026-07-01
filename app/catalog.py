"""Catalog loading, embedding, and search functionality.

Provides hybrid search: semantic (FAISS) + metadata filtering.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import CATALOG_PATH, EMBEDDING_MODEL, TOP_K_RETRIEVAL

logger = logging.getLogger(__name__)


class Assessment:
    """Represents a single SHL assessment from the catalog."""

    def __init__(self, data: dict):
        self.name: str = data.get("name", "")
        self.url: str = data.get("url", "")
        self.description: str = data.get("description", "")
        self.test_type: str = data.get("test_type", "")  # Comma-separated codes like "A,K"
        self.test_type_list: list[str] = [
            t.strip() for t in self.test_type.split(",") if t.strip()
        ]
        self.duration: Optional[int] = data.get("duration")
        self.remote_support: bool = data.get("remote_support", False)
        self.adaptive_support: bool = data.get("adaptive_support", False)
        self.category: str = data.get("category", "")
        self.raw_data: dict = data

    def to_search_text(self) -> str:
        """Create a rich text representation for embedding."""
        parts = [self.name]
        if self.description:
            parts.append(self.description)
        if self.category:
            parts.append(f"Category: {self.category}")
        if self.test_type:
            type_names = self._expand_type_codes()
            if type_names:
                parts.append(f"Type: {', '.join(type_names)}")
        if self.duration:
            parts.append(f"Duration: {self.duration} minutes")
        return ". ".join(parts)

    def to_display_dict(self) -> dict:
        """Return a dict for display in recommendations."""
        return {
            "name": self.name,
            "url": self.url,
            "test_type": self.test_type,
            "description": self.description,
            "duration": self.duration,
            "remote_support": self.remote_support,
            "adaptive_support": self.adaptive_support,
        }

    def _expand_type_codes(self) -> list[str]:
        """Expand test type codes to human-readable names."""
        code_map = {
            "A": "Ability & Aptitude",
            "B": "Biodata & Situational Judgement",
            "C": "Competency",
            "D": "Development",
            "E": "Assessment Exercise",
            "K": "Knowledge & Skills",
            "P": "Personality & Behaviour",
            "S": "Simulation",
        }
        return [code_map.get(c, c) for c in self.test_type_list]

    def __repr__(self) -> str:
        return f"Assessment(name='{self.name}', type='{self.test_type}')"


class CatalogSearch:
    """Manages the assessment catalog with FAISS-based semantic search."""

    def __init__(self):
        self.assessments: list[Assessment] = []
        self.embedder: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.IndexFlatIP] = None
        self._embeddings: Optional[np.ndarray] = None
        self._loaded = False

    def load(self, catalog_path: Optional[Path] = None) -> None:
        """Load catalog from JSON and build search index."""
        path = catalog_path or CATALOG_PATH
        if not path.exists():
            logger.warning(f"Catalog not found at {path}. Using empty catalog.")
            self.assessments = []
            self._loaded = True
            return

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self.assessments = [Assessment(item) for item in raw_data]
        logger.info(f"Loaded {len(self.assessments)} assessments from catalog")

        # Build search index
        self._build_index()
        self._loaded = True

    def _build_index(self) -> None:
        """Build FAISS index from assessment embeddings."""
        if not self.assessments:
            return

        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)

        texts = [a.to_search_text() for a in self.assessments]
        logger.info(f"Encoding {len(texts)} assessments...")
        self._embeddings = self.embedder.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )

        # Build FAISS index (inner product = cosine similarity on normalized vectors)
        dim = self._embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(self._embeddings.astype(np.float32))
        logger.info(f"FAISS index built with {self.index.ntotal} vectors, dim={dim}")

    def search(
        self,
        query: str,
        top_k: int = TOP_K_RETRIEVAL,
        type_filter: Optional[list[str]] = None,
        max_duration: Optional[int] = None,
        remote_required: Optional[bool] = None,
    ) -> list[tuple[Assessment, float]]:
        """Search for assessments matching the query.

        Returns list of (Assessment, score) tuples sorted by relevance.
        """
        if not self.assessments or self.index is None or self.embedder is None:
            return []

        # Encode query
        query_embedding = self.embedder.encode(
            [query], normalize_embeddings=True
        ).astype(np.float32)

        # Search FAISS - get more results than needed for filtering
        search_k = min(top_k * 3, len(self.assessments))
        scores, indices = self.index.search(query_embedding, search_k)

        results: list[tuple[Assessment, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for empty slots
                continue

            assessment = self.assessments[idx]

            # Apply metadata filters
            if type_filter and not any(
                t in assessment.test_type_list for t in type_filter
            ):
                continue

            if max_duration is not None and assessment.duration is not None:
                if assessment.duration > max_duration:
                    continue

            if remote_required is True and not assessment.remote_support:
                continue

            results.append((assessment, float(score)))

            if len(results) >= top_k:
                break

        return results

    def find_by_name(self, name: str) -> Optional[Assessment]:
        """Find an assessment by exact or fuzzy name match."""
        name_lower = name.lower().strip()

        # Exact match
        for a in self.assessments:
            if a.name.lower().strip() == name_lower:
                return a

        # Substring match
        for a in self.assessments:
            if name_lower in a.name.lower() or a.name.lower() in name_lower:
                return a

        # Semantic search as fallback
        results = self.search(name, top_k=1)
        if results and results[0][1] > 0.5:  # reasonable similarity threshold
            return results[0][0]

        return None

    def get_all_urls(self) -> set[str]:
        """Return all valid catalog URLs for validation."""
        return {a.url for a in self.assessments if a.url}

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Global singleton
catalog_search = CatalogSearch()
