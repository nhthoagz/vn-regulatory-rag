"""Dense index bằng `sentence-transformers` (SPEC §7).

Cache theo `model + chunk_sha` để không embed lại; embed trên CPU (GPU 4 GB chỉ dùng khi
được bật rõ ràng). E5 cần tiền tố `passage: `/`query: `, bge-m3 thì không.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODEL_IDS = {
    "bge-m3": "BAAI/bge-m3",
    "e5-large": "intfloat/multilingual-e5-large",
}
PREFIXED = {"e5-large"}


def _slug(name: str) -> str:
    return name.replace("/", "__")


def _with_prefix(texts: list[str], kind: str, model_key: str) -> list[str]:
    if model_key not in PREFIXED:
        return texts
    prefix = "query: " if kind == "query" else "passage: "
    return [f"{prefix}{text}" for text in texts]


@dataclass
class DenseIndex:
    """Ma trận embedding đã chuẩn hoá L2; cosine = tích vô hướng."""

    model_key: str
    model_id: str
    chunk_ids: list[str]
    embeddings: np.ndarray
    chunk_sha: str
    truncated: int = 0
    _model: object | None = None

    @classmethod
    def build(
        cls,
        texts: list[str],
        chunk_ids: list[str],
        model_key: str,
        chunk_sha: str,
        cache_dir: Path,
        device: str = "cpu",
        batch_size: int = 16,
        max_seq_length: int = 512,
    ) -> DenseIndex:
        if model_key not in MODEL_IDS:
            raise ValueError(f"model không hỗ trợ: {model_key}")
        cache_dir.mkdir(parents=True, exist_ok=True)
        npy = cache_dir / f"dense-{_slug(model_key)}-{chunk_sha[:12]}.npy"
        meta_path = npy.with_suffix(".json")
        if npy.is_file() and meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return cls(
                model_key=model_key,
                model_id=meta["model_id"],
                chunk_ids=meta["chunk_ids"],
                embeddings=np.load(npy),
                chunk_sha=chunk_sha,
                truncated=meta.get("truncated", 0),
            )

        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(int(os.environ.get("EMBED_THREADS", "4")))
        model = SentenceTransformer(MODEL_IDS[model_key], device=device)
        model.max_seq_length = max_seq_length
        truncated = sum(1 for text in texts if len(text.split()) > max_seq_length)
        prepared = _with_prefix(texts, "passage", model_key)
        embeddings = model.encode(
            prepared,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).astype(np.float32)

        np.save(npy, embeddings)
        meta_path.write_text(
            json.dumps(
                {
                    "model_key": model_key,
                    "model_id": MODEL_IDS[model_key],
                    "chunk_sha": chunk_sha,
                    "chunk_ids": chunk_ids,
                    "rows": int(embeddings.shape[0]),
                    "dim": int(embeddings.shape[1]),
                    "truncated": truncated,
                    "max_seq_length": max_seq_length,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return cls(
            model_key=model_key,
            model_id=MODEL_IDS[model_key],
            chunk_ids=chunk_ids,
            embeddings=embeddings,
            chunk_sha=chunk_sha,
            truncated=truncated,
        )

    def _encoder(self):
        """Nạp model một lần cho mọi truy vấn (encode lại từng câu rất chậm)."""
        if self._model is None:
            import torch
            from sentence_transformers import SentenceTransformer

            torch.set_num_threads(int(os.environ.get("EMBED_THREADS", "4")))
            self._model = SentenceTransformer(self.model_id, device="cpu")
        return self._model

    def search_batch(self, queries: list[str], top_k: int = 10) -> list[list[tuple[int, float]]]:
        """Encode cả lô truy vấn rồi trả top-k cho từng câu (dùng cho eval/ablation)."""
        if not queries:
            return []
        model = self._encoder()
        vectors = model.encode(
            _with_prefix(queries, "query", self.model_key),
            batch_size=16,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)
        scores = vectors @ self.embeddings.T
        results: list[list[tuple[int, float]]] = []
        for row in scores:
            order = np.argsort(-row)[:top_k]
            results.append([(int(index), float(row[index])) for index in order if row[index] > 0])
        return results

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Trả [(index, score)] giảm dần, chỉ giữ điểm > 0."""
        return self.search_batch([query], top_k=top_k)[0]
