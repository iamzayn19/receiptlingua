"""Model/language-data cache manager.

ReceiptLingua is fully offline at runtime: no engine adapter may reach out
to the network to fetch a missing model or language pack. This module is
the single place that resolves "where should backend data live on disk"
and "is it actually there right now" -- callers that find something
missing must raise :class:`~receiptlingua.engines.errors.ModelNotFoundError`
instead of silently attempting a download.

Cache directory resolution order:
  1. ``RECEIPTLINGUA_CACHE_DIR`` environment variable, if set.
  2. ``$XDG_CACHE_HOME/receiptlingua`` on Linux/macOS if ``XDG_CACHE_HOME``
     is set.
  3. ``~/.cache/receiptlingua`` otherwise (an XDG-ish default that also
     works fine on macOS; we intentionally do not use
     ``~/Library/Caches`` to keep behavior identical across platforms
     the sidecar will run on).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from receiptlingua.engines.errors import ModelNotFoundError

#: Subdirectory (relative to the cache dir) holding Tesseract .traineddata
#: language files that are additional to whatever ships with the system
#: Tesseract install (see docs/adr/0002-ocr-backend-selection.md).
TESSDATA_SUBDIR = "tessdata"


def get_cache_dir() -> Path:
    """Resolve the ReceiptLingua model/language-data cache directory.

    Does not create it -- call :meth:`ensure_exists` when writing.
    """
    env_override = os.environ.get("RECEIPTLINGUA_CACHE_DIR")
    if env_override:
        return Path(env_override).expanduser()

    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "receiptlingua"

    return Path.home() / ".cache" / "receiptlingua"


@dataclass(frozen=True)
class CacheManager:
    """Looks up model/language-data availability without ever touching the network."""

    cache_dir: Path

    @classmethod
    def from_env(cls) -> CacheManager:
        return cls(cache_dir=get_cache_dir())

    def ensure_exists(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def tessdata_dir(self) -> Path:
        return self.cache_dir / TESSDATA_SUBDIR

    def cached_tesseract_languages(self) -> tuple[str, ...]:
        """Language codes with a ``<code>.traineddata`` file in our cache dir.

        Only reflects *our* cache -- the caller is responsible for also
        checking the system Tesseract installation's own tessdata
        directory (``tesseract --list-langs`` / ``TESSDATA_PREFIX``),
        since languages installed system-wide (e.g. via
        ``brew install tesseract-lang``) do not need to be duplicated
        here.
        """
        tessdata = self.tessdata_dir()
        if not tessdata.is_dir():
            return ()
        return tuple(sorted(p.stem for p in tessdata.glob("*.traineddata")))

    def require_tesseract_language(self, lang: str, *, extra_search_dirs: tuple[Path, ...] = ()) -> Path:
        """Return the path to ``<lang>.traineddata`` or raise ModelNotFoundError.

        Checks our own cache dir plus any ``extra_search_dirs`` (e.g. the
        system Tesseract tessdata directory). Never downloads anything.
        """
        candidates = [self.tessdata_dir() / f"{lang}.traineddata"]
        candidates.extend(d / f"{lang}.traineddata" for d in extra_search_dirs)

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        raise ModelNotFoundError(
            backend="tesseract",
            resource=f"{lang}.traineddata",
            search_paths=[str(c) for c in candidates],
        )
