"""Load và validate cấu hình YAML (SPEC §3, §7)."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from src.common.paths import CONFIG_DIR

Role = Literal["original", "consolidated"]
HeaderMode = Literal["none", "true", "placebo"]
ChunkLevel = Literal["leaf", "clause", "article"]
RetrievalMode = Literal["bm25", "dense", "linear", "rrf"]


class DocumentMeta(BaseModel):
    """Metadata một văn bản nguồn. Giá trị chưa xác minh được thì để None."""

    doc_id: str
    file: str
    role: Role
    title: str | None = None
    effective_from: date | None = None
    expected_counts: dict[str, int] | None = None
    identity_marker: str | None = None

    @field_validator("file")
    @classmethod
    def _must_be_pdf(cls, value: str) -> str:
        if not value.endswith(".pdf"):
            raise ValueError(f"file phải là .pdf, nhận {value!r}")
        return value


class DocsConfig(BaseModel):
    as_of: date | None = None
    default_doc_id: str
    documents: list[DocumentMeta]

    @model_validator(mode="after")
    def _default_doc_exists(self) -> DocsConfig:
        ids = [doc.doc_id for doc in self.documents]
        if len(set(ids)) != len(ids):
            raise ValueError(f"doc_id bị trùng: {ids}")
        if self.default_doc_id not in ids:
            raise ValueError(f"default_doc_id {self.default_doc_id!r} không có trong documents")
        return self

    def by_id(self, doc_id: str) -> DocumentMeta:
        for doc in self.documents:
            if doc.doc_id == doc_id:
                return doc
        raise KeyError(doc_id)


class BM25Settings(BaseModel):
    k1: float = 1.5
    b: float = 0.75
    use_two_fields: bool = True


class ChunkSettings(BaseModel):
    level: ChunkLevel = "leaf"
    header_mode: HeaderMode = "none"
    max_tokens: int = 800


class PoolSettings(BaseModel):
    bm25: int = 100
    dense: int = 100
    final: int = 10


class DenseSettings(BaseModel):
    model: str = "BAAI/bge-m3"
    fallback_model: str | None = None
    query_prefix: str = ""
    passage_prefix: str = ""
    batch_size: int = 8


class ExpandSettings(BaseModel):
    include_parent: bool = True
    include_exception_clauses: bool = True
    max_tokens: int = 1600


class RetrievalConfig(BaseModel):
    mode: RetrievalMode = "linear"
    alpha: float = 0.7
    alpha_grid: list[float] = Field(default_factory=list)
    normalization: Literal["minmax", "zscore"] = "minmax"
    rrf_k: int = 60
    bm25: BM25Settings = Field(default_factory=BM25Settings)
    chunk: ChunkSettings = Field(default_factory=ChunkSettings)
    pool: PoolSettings = Field(default_factory=PoolSettings)
    rerank_enabled: bool = False
    dense: DenseSettings = Field(default_factory=DenseSettings)
    expand: ExpandSettings = Field(default_factory=ExpandSettings)

    @field_validator("alpha")
    @classmethod
    def _alpha_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"alpha phải trong [0, 1], nhận {value}")
        return value


class ProviderConfig(BaseModel):
    """Một nhà cung cấp OpenAI-compatible. Chỉ tên biến ENV, không chứa secret."""

    base_url_env: str
    api_key_env: str
    model_env: str
    default_base_url: str | None = None
    default_model: str | None = None
    temperature: float = 0.0
    timeout_s: int = 60
    max_retries: int = 2

    @field_validator("api_key_env")
    @classmethod
    def _key_env_name(cls, value: str) -> str:
        if not value.endswith("_API_KEY"):
            raise ValueError(f"api_key_env phải kết thúc bằng _API_KEY, nhận {value!r}")
        return value


class BudgetSettings(BaseModel):
    max_llm_calls: int = 2

    @field_validator("max_llm_calls")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_llm_calls phải >= 1")
        return value


class LLMConfig(BaseModel):
    budget: BudgetSettings = Field(default_factory=BudgetSettings)
    providers: dict[str, ProviderConfig]

    @field_validator("providers")
    @classmethod
    def _has_primary(cls, value: dict[str, ProviderConfig]) -> dict[str, ProviderConfig]:
        if "A" not in value:
            raise ValueError("phải có provider 'A' (generator)")
        return value


class ThresholdsConfig(BaseModel):
    """Ngưỡng OOS trên điểm thô. null = chưa hiệu chỉnh, không được dùng như số thật."""

    calibrated: bool = False
    bm25_min_score: float | None = None
    dense_min_cosine: float | None = None
    rerank_min_logit: float | None = None
    margin_ratio: float | None = None
    calibration_run: str | None = None

    @model_validator(mode="after")
    def _calibrated_means_filled(self) -> ThresholdsConfig:
        if self.calibrated and self.dense_min_cosine is None and self.bm25_min_score is None:
            raise ValueError("calibrated=true nhưng không có ngưỡng nào được điền")
        return self


class SynonymsConfig(BaseModel):
    synonyms: dict[str, list[str]]

    @field_validator("synonyms")
    @classmethod
    def _non_empty(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if not value:
            raise ValueError("synonyms rỗng")
        for key, variants in value.items():
            if key != key.lower():
                raise ValueError(f"khóa synonyms phải viết thường: {key!r}")
            if not variants:
                raise ValueError(f"synonyms[{key!r}] rỗng")
        return value


class IntentExamples(BaseModel):
    examples: list[str] = Field(min_length=1)


class IntentsConfig(BaseModel):
    intents: dict[str, IntentExamples]

    @field_validator("intents")
    @classmethod
    def _known_intents(cls, value: dict[str, IntentExamples]) -> dict[str, IntentExamples]:
        allowed = {"qa", "calc_overtime", "calc_leave", "oos"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"intent không hợp lệ: {sorted(unknown)}")
        missing = {"qa", "oos"} - set(value)
        if missing:
            raise ValueError(f"thiếu intent bắt buộc: {sorted(missing)}")
        return value


class OcrFix(BaseModel):
    pattern: str
    replacement: str
    note: str | None = None


class OcrFixesConfig(BaseModel):
    version: int
    rules: list[OcrFix] = Field(default_factory=list)


class Settings(BaseModel):
    """Toàn bộ cấu hình đã validate."""

    docs: DocsConfig
    retrieval: RetrievalConfig
    llm: LLMConfig
    thresholds: ThresholdsConfig
    synonyms: SynonymsConfig
    intents: IntentsConfig
    ocr_fixes: OcrFixesConfig


def _read_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"không tìm thấy config: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} phải là một mapping YAML")
    return data


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Đọc và validate toàn bộ config một lần cho mỗi tiến trình."""
    return Settings(
        docs=DocsConfig.model_validate(_read_yaml("docs.yaml")),
        retrieval=RetrievalConfig.model_validate(_read_yaml("retrieval.yaml")),
        llm=LLMConfig.model_validate(_read_yaml("llm.yaml")),
        thresholds=ThresholdsConfig.model_validate(_read_yaml("thresholds.yaml")),
        synonyms=SynonymsConfig.model_validate(_read_yaml("synonyms.yaml")),
        intents=IntentsConfig.model_validate(_read_yaml("intents.yaml")),
        ocr_fixes=OcrFixesConfig.model_validate(_read_yaml("ocr_fixes.yaml")),
    )


def clear_settings_cache() -> None:
    """Xóa cache để test có thể đọc lại config sau khi sửa file."""
    load_settings.cache_clear()


def load_documents() -> list[DocumentMeta]:
    return list(load_settings().docs.documents)