from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.common.config import (
    DocsConfig,
    DocumentMeta,
    IntentsConfig,
    LLMConfig,
    ProviderConfig,
    ThresholdsConfig,
    load_settings,
)


def test_settings_load_from_repo_config() -> None:
    settings = load_settings()
    assert len(settings.docs.documents) == 2
    assert settings.docs.default_doc_id == "18-VBHN-VPQH-2026"
    assert settings.retrieval.mode in {"bm25", "dense", "linear", "rrf"}
    assert 0.0 <= settings.retrieval.alpha <= 1.0


def test_llm_config_holds_env_names_only() -> None:
    settings = load_settings()
    for name, provider in settings.llm.providers.items():
        assert provider.api_key_env.endswith("_API_KEY"), name
        assert provider.api_key_env.startswith("VN_RAG_")
        # Không được có giá trị secret nào trong file config.
        dumped = provider.model_dump()
        for value in dumped.values():
            assert not (isinstance(value, str) and value.startswith("sk-")), name


def test_thresholds_are_not_fake_calibrated() -> None:
    thresholds = load_settings().thresholds
    if not thresholds.calibrated:
        assert thresholds.dense_min_cosine is None
        assert thresholds.bm25_min_score is None
        assert thresholds.rerank_min_logit is None
        assert thresholds.margin_ratio is None


def test_ocr_fixes_are_versioned() -> None:
    settings = load_settings()
    assert settings.ocr_fixes.version >= 1


def test_synonyms_and_intents_are_populated() -> None:
    settings = load_settings()
    assert len(settings.synonyms.synonyms) >= 10
    assert {"qa", "oos"} <= set(settings.intents.intents)


def test_default_doc_must_exist() -> None:
    doc = DocumentMeta(doc_id="X", file="x.pdf", role="original")
    with pytest.raises(ValidationError):
        DocsConfig(default_doc_id="Y", documents=[doc])


def test_duplicate_doc_ids_rejected() -> None:
    doc = DocumentMeta(doc_id="X", file="x.pdf", role="original")
    with pytest.raises(ValidationError):
        DocsConfig(default_doc_id="X", documents=[doc, doc])


def test_llm_requires_provider_a() -> None:
    provider = ProviderConfig(
        base_url_env="VN_RAG_LLM_B_BASE_URL",
        api_key_env="VN_RAG_LLM_B_API_KEY",
        model_env="VN_RAG_LLM_B_MODEL",
    )
    with pytest.raises(ValidationError):
        LLMConfig(providers={"B": provider})


def test_calibrated_without_thresholds_rejected() -> None:
    with pytest.raises(ValidationError):
        ThresholdsConfig(calibrated=True)


def test_unknown_intent_rejected() -> None:
    intents = {
        "qa": {"examples": ["x"]},
        "oos": {"examples": ["y"]},
        "calc": {"examples": ["z"]},
    }
    with pytest.raises(ValidationError):
        IntentsConfig(intents=intents)