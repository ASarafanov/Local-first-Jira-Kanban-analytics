from __future__ import annotations

import json
import subprocess
from pathlib import Path


class RuntimeStore:
    def __init__(self, service_name: str, fallback_path: Path) -> None:
        self.service_name = service_name
        self.fallback_path = fallback_path
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, secret: str) -> str:
        if not secret:
            return ""
        if self._store_in_keychain(key, secret):
            return f"keychain:{key}"
        self._store_in_file(key, secret)
        return f"file:{key}"

    def get(self, ref: str | None) -> str | None:
        if not ref:
            return None
        if ":" not in ref:
            return ref
        source, key = ref.split(":", 1)
        if source == "keychain":
            return self._read_from_keychain(key)
        if source == "file":
            return self._read_from_file(key)
        return ref

    def delete(self, ref: str | None) -> None:
        if not ref or ":" not in ref:
            return
        source, key = ref.split(":", 1)
        if source == "keychain":
            self._delete_from_keychain(key)
            return
        if source == "file":
            self._delete_from_file(key)

    def _store_in_keychain(self, key: str, secret: str) -> bool:
        try:
            subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-U",
                    "-a",
                    key,
                    "-s",
                    self.service_name,
                    "-w",
                    secret,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except Exception:
            return False

    def _read_from_keychain(self, key: str) -> str | None:
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-a",
                    key,
                    "-s",
                    self.service_name,
                    "-w",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() or None
        except Exception:
            return None

    def _delete_from_keychain(self, key: str) -> None:
        try:
            subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-a",
                    key,
                    "-s",
                    self.service_name,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return

    def _store_in_file(self, key: str, secret: str) -> None:
        payload = self._load_file()
        payload[key] = secret
        self.fallback_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.fallback_path.chmod(0o600)

    def _read_from_file(self, key: str) -> str | None:
        payload = self._load_file()
        return payload.get(key)

    def _delete_from_file(self, key: str) -> None:
        payload = self._load_file()
        if key not in payload:
            return
        payload.pop(key, None)
        self.fallback_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.fallback_path.chmod(0o600)

    def _load_file(self) -> dict[str, str]:
        if not self.fallback_path.exists():
            return {}
        try:
            return json.loads(self.fallback_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
