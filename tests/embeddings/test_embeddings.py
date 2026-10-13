"""Embedding pipeline tests: reuse rule, input context, and pinned dimensions.

No model is loaded (a stub encoder is injected) and no database is touched, so
these run offline and fast.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from embeddings.encoder import EMBEDDING_DIM, MODEL_NAME, SentenceTransformerEncoder
from embeddings.pipeline import (
    embedding_input,
    select_missing,
    to_vector_literal,
    verify_complete,
)


@pytest.mark.parametrize("dimension", [EMBEDDING_DIM, None])
def test_encoder_requires_a_known_dimension(monkeypatch, dimension):
    model = SimpleNamespace(get_embedding_dimension=lambda: dimension)

    def load_model(name, *, device):
        assert name == MODEL_NAME
        assert device == "cpu"
        return model

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        SimpleNamespace(SentenceTransformer=load_model))
    if dimension is None:
        with pytest.raises(ValueError, match="does not report its dimension"):
            SentenceTransformerEncoder()
    else:
        assert SentenceTransformerEncoder().dim == dimension


def test_select_missing_reuses_matching_content_version():
    passages = [
        {"passage_hash": "a", "processing_version": "v1", "section": None, "text": "x"},
        {"passage_hash": "b", "processing_version": "v1", "section": None, "text": "y"},
        {"passage_hash": "a", "processing_version": "v2", "section": None, "text": "x"},
    ]
    existing = {("a", "v1")}
    missing = select_missing(passages, existing)
    # "a"/v1 is reused; the same hash under v2 and the new hash both embed.
    assert {(p["passage_hash"], p["processing_version"]) for p in missing} == {("b", "v1"), ("a", "v2")}


def test_embedding_input_prefixes_section_for_context():
    assert embedding_input({"section": "Item 7.", "text": "sales rose"}) == "Item 7.\nsales rose"
    assert embedding_input({"section": None, "text": "cover"}) == "cover"


def test_vector_literal_formats_pgvector_input():
    assert to_vector_literal([0.5, -1.0]) == "[0.5,-1.0]"


def test_verify_complete_rejects_unembedded_passages():
    passages = [{"passage_hash": "a", "processing_version": "v1", "section": None, "text": "x"}]
    verify_complete(passages, {("a", "v1")})  # all embedded: fine
    with pytest.raises(RuntimeError, match="no embedding"):
        verify_complete(passages, set())


def test_pinned_model_matches_dbt_vars():
    from extraction import PROCESSING_VERSION

    project = Path(__file__).resolve().parents[2] / "dbt" / "dbt_project.yml"
    text = project.read_text()
    assert f'embedding_model_version: "{MODEL_NAME}"' in text
    assert f"embedding_dim: {EMBEDDING_DIM}" in text
    assert f'active_processing_version: "{PROCESSING_VERSION}"' in text
