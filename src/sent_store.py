"""
Persistent Flash News dedup store.

In-memory sets alone reset on every scheduler restart, which re-sends
the same headline+source within the scan window. This JSON file survives restarts.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set

from loguru import logger

from config.settings import BASE_DIR

DEFAULT_PATH = BASE_DIR / "data" / "sent_flash.json"
MAX_ENTRIES = 500


class SentFlashStore:
    """Thread-safe fingerprint store keyed by md5(title_en|source)."""

    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_PATH
        self._lock = threading.Lock()
        self._sent: Dict[str, str] = {}  # fingerprint -> ISO timestamp
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._sent = {str(k): str(v) for k, v in raw.items()}
                elif isinstance(raw, list):
                    now = datetime.now(timezone.utc).isoformat()
                    self._sent = {str(k): now for k in raw}
                logger.info(f"Loaded {len(self._sent)} sent flash fingerprints from {self.path}")
            else:
                self._sent = {}
        except Exception as e:
            logger.warning(f"Could not load sent flash store: {e}")
            self._sent = {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            items = sorted(self._sent.items(), key=lambda kv: kv[1], reverse=True)
            trimmed = dict(items[:MAX_ENTRIES])
            self._sent = trimmed
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(trimmed, ensure_ascii=False, indent=0), encoding="utf-8")
            tmp.replace(self.path)
        except Exception as e:
            logger.error(f"Could not save sent flash store: {e}")

    def has(self, fingerprint: str) -> bool:
        with self._lock:
            return fingerprint in self._sent

    def add(self, fingerprint: str) -> bool:
        """Mark fingerprint as sent. Returns True if newly added, False if already present."""
        with self._lock:
            if fingerprint in self._sent:
                return False
            self._sent[fingerprint] = datetime.now(timezone.utc).isoformat()
            self._save()
            return True

    def known(self) -> Set[str]:
        with self._lock:
            return set(self._sent.keys())
