
import base64
import hashlib
import json
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class GoogleTokenError(Exception):
    pass


def _fernet() -> Fernet:
    secret = (
        settings.google_token_encryption_key
        or settings.jwt_secret_key
    )

    if not secret:
        raise GoogleTokenError("Google token encryption key is missing.")

    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _token_path(student_id: UUID) -> Path:
    directory = Path(settings.google_token_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{student_id}.token"


def save_google_token(student_id: UUID, token_data: dict) -> None:
    try:
        raw = json.dumps(token_data).encode("utf-8")
        encrypted = _fernet().encrypt(raw)

        path = _token_path(student_id)
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_bytes(encrypted)
        temporary_path.replace(path)
    except Exception as exc:
        raise GoogleTokenError(
            "Could not save Google credentials."
        ) from exc


def load_google_token(student_id: UUID) -> dict | None:
    path = _token_path(student_id)

    if not path.exists():
        return None

    try:
        encrypted = path.read_bytes()
        raw = _fernet().decrypt(encrypted)
        return json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, OSError) as exc:
        raise GoogleTokenError(
            "Stored Google credentials could not be decrypted."
        ) from exc


def delete_google_token(student_id: UUID) -> bool:
    path = _token_path(student_id)

    if path.exists():
        path.unlink()
        return True

    return False
