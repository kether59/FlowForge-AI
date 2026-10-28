"""Extraction de texte depuis les fichiers uploadés (PDF / TXT / MD / CSV)."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from app.config import DATA_DIR
from app.schemas import SourceDocument

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class UploadTooLargeError(ValueError):
    """Raised when an upload exceeds the configured size limit."""


def extract_text(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if lower.endswith((".txt", ".md", ".csv", ".json", ".log", ".yaml", ".yml")):
        return content.decode("utf-8", errors="ignore")
    raise ValueError(f"Extension non supportée: {filename}. Utilisez PDF, TXT, MD, CSV ou JSON.")


def _extract_file(path: Path) -> str:
    lower = path.name.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if lower.endswith((".txt", ".md", ".csv", ".json", ".log", ".yaml", ".yml")):
        return path.read_bytes().decode("utf-8", errors="ignore")
    raise ValueError(f"Extension non supportée: {path.name}. Utilisez PDF, TXT, MD, CSV ou JSON.")


def _source_document(file_id: str, filename: str, text: str, size: int) -> SourceDocument:
    if not text.strip():
        raise ValueError(
            "Aucun texte extractible. Le PDF est peut-être scanné ; l’OCR n’est pas encore pris en charge."
        )
    stored_as = f"{file_id}_{Path(filename).name}"
    return SourceDocument(
        id=file_id,
        name=Path(filename).name,
        text=text,
        source="upload",
        metadata={"size": size, "storedAs": stored_as},
    )


def save_upload_stream(filename: str, stream: BinaryIO, max_bytes: int) -> SourceDocument:
    safe_name = Path(filename).name
    file_id = "file_" + uuid.uuid4().hex[:10]
    path = UPLOAD_DIR / f"{file_id}_{safe_name}"
    size = 0
    try:
        with path.open("wb") as target:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    limit_mb = max_bytes // (1024 * 1024)
                    raise UploadTooLargeError(
                        f"Fichier trop volumineux : limite de {limit_mb} Mo."
                    )
                target.write(chunk)
        if size == 0:
            raise ValueError("Fichier vide")
        return _source_document(file_id, safe_name, _extract_file(path), size)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def load_uploaded(file_id: str) -> SourceDocument | None:
    for path in UPLOAD_DIR.glob(f"{file_id}_*"):
        try:
            text = _extract_file(path)
        except Exception:
            continue
        return SourceDocument(
            id=file_id,
            name=path.name.split("_", 1)[1],
            text=text,
            source="upload",
            metadata={"size": path.stat().st_size},
        )
    return None


def list_uploads() -> list[dict[str, Any]]:
    files = []
    for path in sorted(UPLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if "_" not in path.name:
            continue
        file_id, name = path.name.split("_", 1)
        files.append(
            {
                "id": file_id,
                "name": name,
                "size": path.stat().st_size,
                "uploadedAt": path.stat().st_mtime,
            }
        )
    return files
