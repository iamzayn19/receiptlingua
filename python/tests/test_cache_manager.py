"""Cache manager tests: cache dir resolution and offline missing-model behavior.

No network call must ever be attempted when a model/language file is
missing -- callers get a MODEL_NOT_FOUND EngineError instead.
"""

from __future__ import annotations

import socket

import pytest

from receiptlingua.engines.cache import CacheManager, get_cache_dir
from receiptlingua.engines.errors import ModelNotFoundError


def test_get_cache_dir_respects_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("RECEIPTLINGUA_CACHE_DIR", str(tmp_path / "custom"))
    assert get_cache_dir() == tmp_path / "custom"


def test_get_cache_dir_respects_xdg_cache_home(monkeypatch, tmp_path):
    monkeypatch.delenv("RECEIPTLINGUA_CACHE_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert get_cache_dir() == tmp_path / "receiptlingua"


def test_get_cache_dir_default_falls_back_to_home_cache(monkeypatch):
    monkeypatch.delenv("RECEIPTLINGUA_CACHE_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    result = get_cache_dir()
    assert result.parts[-2:] == (".cache", "receiptlingua")


def test_cached_tesseract_languages_empty_when_dir_absent(tmp_path):
    manager = CacheManager(cache_dir=tmp_path / "does-not-exist")
    assert manager.cached_tesseract_languages() == ()


def test_cached_tesseract_languages_lists_present_traineddata_files(tmp_path):
    manager = CacheManager(cache_dir=tmp_path)
    manager.ensure_exists()
    tessdata = manager.tessdata_dir()
    tessdata.mkdir(parents=True)
    (tessdata / "tam.traineddata").write_bytes(b"fake")
    (tessdata / "ara.traineddata").write_bytes(b"fake")

    assert manager.cached_tesseract_languages() == ("ara", "tam")


def test_require_tesseract_language_raises_model_not_found_when_missing(tmp_path):
    manager = CacheManager(cache_dir=tmp_path)

    with pytest.raises(ModelNotFoundError) as exc_info:
        manager.require_tesseract_language("tam")

    assert exc_info.value.code == "MODEL_NOT_FOUND"
    assert exc_info.value.details["resource"] == "tam.traineddata"


def test_require_tesseract_language_missing_never_touches_the_network(tmp_path, monkeypatch):
    """A missing model must raise, not attempt any socket connection."""

    def _blocked_socket(*args, **kwargs):
        raise AssertionError("network access attempted while resolving a missing model")

    monkeypatch.setattr(socket, "socket", _blocked_socket)
    manager = CacheManager(cache_dir=tmp_path)

    with pytest.raises(ModelNotFoundError):
        manager.require_tesseract_language("tam")


def test_require_tesseract_language_found_in_own_cache(tmp_path):
    manager = CacheManager(cache_dir=tmp_path)
    manager.ensure_exists()
    tessdata = manager.tessdata_dir()
    tessdata.mkdir(parents=True)
    target = tessdata / "tam.traineddata"
    target.write_bytes(b"fake")

    assert manager.require_tesseract_language("tam") == target


def test_require_tesseract_language_found_in_extra_search_dir(tmp_path):
    manager = CacheManager(cache_dir=tmp_path / "empty-cache")
    system_dir = tmp_path / "system-tessdata"
    system_dir.mkdir()
    target = system_dir / "eng.traineddata"
    target.write_bytes(b"fake")

    assert manager.require_tesseract_language("eng", extra_search_dirs=(system_dir,)) == target
