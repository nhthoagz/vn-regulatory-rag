"""Tải trọng số model embedding về `HF_HOME` (SPEC §7). Chạy bằng nohup vì > 60 s."""

from __future__ import annotations

import sys

from huggingface_hub import snapshot_download

from src.retrieval.dense import MODEL_IDS

ALLOW = [
    "*.json", "*.txt", "*.model", "*.safetensors", "*.bin",
    "tokenizer*", "sentencepiece*", "*.spm", "vocab*", "*.md",
]
IGNORE = ["*.onnx", "onnx/*", "*.ot", "*.h5", "*.msgpack", "openvino/*", "coreml/*", "*.gguf"]


def main(argv: list[str] | None = None) -> int:
    keys = argv or ["bge-m3", "e5-large"]
    for key in keys:
        if key not in MODEL_IDS:
            print(f"bỏ qua model lạ: {key}")
            continue
        model_id = MODEL_IDS[key]
        print(f"tải {key} = {model_id} ...", flush=True)
        path = snapshot_download(model_id, allow_patterns=ALLOW, ignore_patterns=IGNORE)
        print(f"OK {key} -> {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
