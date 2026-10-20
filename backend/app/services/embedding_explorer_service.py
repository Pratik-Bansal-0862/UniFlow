from __future__ import annotations

from typing import Any

import numpy as np

from app.integrations.chroma_vector_store import ChromaVectorStore


class EmbeddingExplorerService:
    """Projects the authenticated student's existing Chroma vectors with deterministic PCA."""

    def __init__(self, vector_store: ChromaVectorStore | None = None) -> None:
        self.vector_store = vector_store or ChromaVectorStore()

    def get_projection(self, student_id: str, limit: int = 500) -> dict[str, Any]:
        # Always scope the query in Chroma itself; never accept student_id from request input.
        collection = self.vector_store.collection
        result = collection.get(
            where={"student_id": student_id},
            include=["documents", "metadatas", "embeddings"],
            limit=limit,
        )
        ids = result.get("ids") or []
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        vectors = result.get("embeddings")
        if not ids or vectors is None:
            return {
                "method": "PCA",
                "note": "Coordinates are a 3D projection of stored embeddings, not literal semantic axes.",
                "total": 0,
                "points": [],
            }

        matrix = np.asarray(vectors, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[0] != len(ids):
            raise ValueError("Stored embeddings have an unexpected shape")
        # Center vectors, then use SVD for deterministic principal components.
        centered = matrix - matrix.mean(axis=0, keepdims=True)
        if matrix.shape[0] == 1:
            coords = np.zeros((1, 3), dtype=np.float64)
        else:
            _u, _s, vt = np.linalg.svd(centered, full_matrices=False)
            components = min(3, vt.shape[0])
            coords = centered @ vt[:components].T
            if components < 3:
                coords = np.pad(coords, ((0, 0), (0, 3 - components)))
        # Keep PCA coordinates in their natural scale so component variance remains meaningful.
        # The visualization scales the display bounds, not the underlying coordinates.

        points = []
        for index, chunk_id in enumerate(ids):
            meta = metas[index] if index < len(metas) and metas[index] else {}
            document_id = str(meta.get("document_id") or "")
            source_name = str(meta.get("source_name") or "Untitled source")
            text = str(docs[index] or "") if index < len(docs) else ""
            points.append({
                "id": str(chunk_id),
                "document_id": document_id,
                "source_name": source_name,
                "chunk_index": int(meta.get("chunk_index") or 0),
                "page_number": meta.get("page_number"),
                "preview": text[:500],
                "x": round(float(coords[index, 0]), 5),
                "y": round(float(coords[index, 1]), 5),
                "z": round(float(coords[index, 2]), 5),
            })
        return {
            "method": "PCA",
            "note": "Each point is an existing indexed chunk. PCA compresses high-dimensional embeddings to 3 axes; axis values have no standalone meaning.",
            "total": len(points),
            "points": points,
        }
