"""Giao diện Gradio tối giản (SPEC §10) — cài `gradio` mới chạy được.

Chạy: `uv run python -m src.ui.gradio_app` (cần `uv pip install gradio`).
Không import gradio ở cấp module để test nhanh không phụ thuộc gói nặng này.
"""

from __future__ import annotations

from src.common.config import load_settings
from src.common.paths import INDEX_DIR, PROCESSED_DIR
from src.core.pipeline import Pipeline

_cache: dict[str, Pipeline] = {}


def get_pipeline() -> Pipeline:
    if "default" not in _cache:
        settings = load_settings()
        _cache["default"] = Pipeline(
            chunks_path=PROCESSED_DIR / "chunks_leaf.jsonl",
            nodes_path=PROCESSED_DIR / "nodes.jsonl",
            fallback_path=INDEX_DIR / "fallback_map.json",
            default_doc_id=settings.docs.default_doc_id,
        )
    return _cache["default"]


def answer(question: str) -> tuple[str, str]:
    """Trả (câu trả lời, khối trích dẫn) cho giao diện."""
    result = get_pipeline().ask(question)
    citations = "\n".join(f"- {item}" for item in dict.fromkeys(result.citations))
    warnings = "\n".join(f"⚠️ {item}" for item in result.warnings)
    text = result.answer if not warnings else f"{result.answer}\n\n{warnings}"
    return text, citations or "(không có trích dẫn)"


def main() -> None:
    import gradio as gr

    demo = gr.Interface(
        fn=answer,
        inputs=gr.Textbox(label="Câu hỏi", lines=2),
        outputs=[gr.Textbox(label="Trả lời", lines=10), gr.Textbox(label="Trích dẫn", lines=4)],
        title="vn-regulatory-rag — Bộ luật Lao động 2019",
        description="Trả lời có trích dẫn Điều/Khoản/Điểm; ngoài phạm vi thì từ chối.",
    )
    demo.launch()


if __name__ == "__main__":
    main()