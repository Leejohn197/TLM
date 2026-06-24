from __future__ import annotations

import base64
import os


class PasswordCipher:
    """Small encryption boundary for phase one.

    Real deployments should replace the fallback with Keychain or a managed
    AES key before storing production-like credentials.
    """

    def __init__(self) -> None:
        self._key = os.environ.get("TLM_MASTER_KEY", "")

    def encrypt(self, plain_text: str) -> str:
        if not plain_text:
            return ""
        payload = plain_text.encode("utf-8")
        if self._key:
            payload = self._xor(payload, self._key.encode("utf-8"))
            return "enc:v1:" + base64.urlsafe_b64encode(payload).decode("ascii")
        return "dev:v1:" + base64.urlsafe_b64encode(payload).decode("ascii")

    def decrypt(self, cipher_text: str) -> str:
        if not cipher_text:
            return ""
        try:
            if cipher_text.startswith("enc:v1:"):
                if not self._key:
                    raise ValueError("TLM_MASTER_KEY is required to decrypt this password")
                payload = base64.urlsafe_b64decode(cipher_text.removeprefix("enc:v1:"))
                return self._xor(payload, self._key.encode("utf-8")).decode("utf-8")
            if cipher_text.startswith("dev:v1:"):
                payload = base64.urlsafe_b64decode(cipher_text.removeprefix("dev:v1:"))
                return payload.decode("utf-8")
        except Exception as exc:  # pragma: no cover - defensive boundary
            raise ValueError("Unable to decrypt stored password") from exc
        raise ValueError("Unsupported password format")

    @staticmethod
    def mask(_: str) -> str:
        return "••••••••"

    @staticmethod
    def _xor(payload: bytes, key: bytes) -> bytes:
        if not key:
            return payload
        return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(payload))
