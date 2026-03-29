"""Tests for consolidated configuration logic."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from whati8.config import (
    SearchSettings,
    Settings,
    TomlConfigSettingsSource,
)


def test_settings_search_structure():
    """Verify default search settings when no config.toml exists."""
    settings = Settings()

    # We expect this new structure
    assert hasattr(settings, "search")
    assert hasattr(settings.search, "rerank")

    # Default values
    assert settings.search.keyword_weight == 0.5
    assert settings.search.semantic_weight == 0.5
    assert settings.search.rerank.strategy == "word_count"
    assert settings.search.rerank.word_threshold == 3
    assert settings.search.rerank.confidence_threshold == 0.6
    assert settings.search.rerank.top_k == 10
    assert settings.search.rerank.max_candidates == 50


def test_settings_env_overrides():
    """Verify that environment variables can override search settings."""
    # Pydantic Settings uses nested env vars like SEARCH__KEYWORD_WEIGHT
    # Or SEARCH_KEYWORD_WEIGHT if using env_nested_delimiter="__"
    with patch.dict(
        os.environ,
        {
            "SEARCH__KEYWORD_WEIGHT": "0.7",
            "SEARCH__RERANK__STRATEGY": "always",
            "SEARCH__RERANK__TOP_K": "25",
        },
    ):
        settings = Settings()
        assert settings.search.keyword_weight == 0.7
        assert settings.search.rerank.strategy == "always"
        assert settings.search.rerank.top_k == 25


def test_settings_toml_loading():
    """Verify that config.toml (if present) overrides defaults."""
    toml_data = {
        "search": {
            "keyword_weight": 0.8,
            "semantic_weight": 0.2,
            "rerank": {
                "strategy": "confidence",
                "word_threshold": 5,
                "confidence_threshold": 0.4,
                "top_k": 15,
                "max_candidates": 100,
            },
        }
    }
    with patch.object(TomlConfigSettingsSource, "_load_toml", return_value=toml_data):
        settings = Settings()
        assert settings.search.keyword_weight == 0.8
        assert settings.search.semantic_weight == 0.2
        assert settings.search.rerank.strategy == "confidence"
        assert settings.search.rerank.word_threshold == 5
        assert settings.search.rerank.confidence_threshold == 0.4
        assert settings.search.rerank.top_k == 15
        assert settings.search.rerank.max_candidates == 100


def test_env_overrides_toml():
    """Env vars should take priority over config.toml values.

    Note: pydantic-settings with env_nested_delimiter replaces the entire
    nested object when any env var for that prefix is set. So setting
    SEARCH__KEYWORD_WEIGHT means the env source provides the whole search
    model (with defaults for unset fields), overriding the TOML source.
    """
    toml_data = {
        "search": {
            "keyword_weight": 0.8,
            "semantic_weight": 0.2,
        }
    }
    with (
        patch.object(TomlConfigSettingsSource, "_load_toml", return_value=toml_data),
        patch.dict(
            os.environ,
            {
                "SEARCH__KEYWORD_WEIGHT": "0.3",
                "SEARCH__SEMANTIC_WEIGHT": "0.7",
            },
        ),
    ):
        settings = Settings()
        # Env wins over TOML
        assert settings.search.keyword_weight == 0.3
        assert settings.search.semantic_weight == 0.7


def test_partial_toml_no_rerank():
    """TOML with [search] but no [search.rerank] uses defaults for rerank."""
    toml_data = {
        "search": {
            "keyword_weight": 0.6,
            "semantic_weight": 0.4,
        }
    }
    with patch.object(TomlConfigSettingsSource, "_load_toml", return_value=toml_data):
        settings = Settings()
        assert settings.search.keyword_weight == 0.6
        assert settings.search.rerank.strategy == "word_count"
        assert settings.search.rerank.top_k == 10


def test_missing_toml_uses_defaults():
    """Empty TOML (missing file) falls back to all defaults."""
    with patch.object(TomlConfigSettingsSource, "_load_toml", return_value={}):
        settings = Settings()
        assert settings.search.keyword_weight == 0.5
        assert settings.search.semantic_weight == 0.5
        assert settings.search.rerank.strategy == "word_count"


def test_malformed_toml_uses_defaults():
    """Malformed TOML should be caught and return defaults (not crash)."""
    # _load_toml handles TOMLDecodeError internally and returns {}
    with patch.object(TomlConfigSettingsSource, "_load_toml", return_value={}):
        settings = Settings()
        assert settings.search.keyword_weight == 0.5


def test_weight_validation_bounds():
    """Weight values must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        SearchSettings(keyword_weight=-0.1)
    with pytest.raises(ValidationError):
        SearchSettings(keyword_weight=1.5)
    with pytest.raises(ValidationError):
        SearchSettings(semantic_weight=-0.1)
    with pytest.raises(ValidationError):
        SearchSettings(semantic_weight=1.5)

    # Edge cases that should be valid
    valid = SearchSettings(keyword_weight=0.0, semantic_weight=1.0)
    assert valid.keyword_weight == 0.0
    assert valid.semantic_weight == 1.0


def test_parse_search_helper():
    """TomlConfigSettingsSource._parse_search returns None for missing section."""
    assert TomlConfigSettingsSource._parse_search({}) is None
    assert TomlConfigSettingsSource._parse_search({"other": 1}) is None

    result = TomlConfigSettingsSource._parse_search({"search": {"keyword_weight": 0.7}})
    assert result is not None
    assert result.keyword_weight == 0.7
    assert result.semantic_weight == 0.5  # default
