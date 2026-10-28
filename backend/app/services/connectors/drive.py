"""Connecteur Google Drive.

Deux modes :
1. **Réel** — si `google-api-python-client` + `google-auth` sont installés et
   qu'un fichier de credentials de service account est fourni, on liste et
   télécharge les Google Docs exportés en texte / les .txt / .pdf.
2. **Démo** — sinon, on renvoie un jeu de documents factices pour que le
   workflow reste exécutable sans configuration externe.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas import SourceDocument

DEMO_DOCS = [
    {
        "id": "drive-demo-politique",
        "name": "Politique_qualite_interne.txt",
        "text": (
            "Politique qualité interne — FlowForge SAS\n\n"
            "Tout incident de production doit être qualifié sous 4 heures ouvrées. "
            "Les incidents critiques (P1) déclenchent une cellule de crise animée par l'astreinte SRE. "
            "Un post-mortem sans blâme est obligatoire dans les 5 jours ouvrés suivant la résolution.\n\n"
            "Les demandes de changement passent par une revue le mardi. Un changement à risque élevé "
            "nécessite l'approbation de deux ingénieurs seniors et d'un responsable produit."
        ),
    },
    {
        "id": "drive-demo-onboarding",
        "name": "Guide_onboarding_client.txt",
        "text": (
            "Guide d'onboarding client\n\n"
            "Étape 1 : atelier de cadrage (90 minutes) pour cartographier les processus métier. "
            "Étape 2 : connexion des sources documentaires (Drive, Confluence, SharePoint). "
            "Étape 3 : conception des assistants et validation des garde-fous.\n\n"
            "Le délai standard d'onboarding est de trois semaines. Le support est disponible "
            "de 9h à 18h CET du lundi au vendredi, avec une astreinte pour les clients Enterprise."
        ),
    },
    {
        "id": "drive-demo-rgpd",
        "name": "Note_RGPD_IA.txt",
        "text": (
            "Note RGPD et IA générative\n\n"
            "Les données envoyées aux modèles doivent être minimisées et pseudonymisées lorsque "
            "cela est possible. Les journaux d'exécution sont conservés 30 jours. "
            "Les fournisseurs LLM doivent présenter des garanties de non-entraînement sur les données clients.\n\n"
            "Tout traitement impliquant des données sensibles (santé, RH) requiert une analyse d'impact (AIPD)."
        ),
    },
]


def _credentials_path(explicit: str | None) -> Path | None:
    raw = explicit or get_settings().google_drive_credentials
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None


def _real_available(cred: Path | None) -> bool:
    if not cred:
        return False
    try:
        import googleapiclient.discovery  # noqa: F401
        import google.oauth2.service_account  # noqa: F401
    except ImportError:
        return False
    return True


def _build_service(cred: Path):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(cred.read_text())
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _export_google_doc(service, file_id: str) -> str:
    data = service.files().export(fileId=file_id, mimeType="text/plain").execute()
    return data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else str(data)


def _download_text_file(service, file_id: str) -> str:
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8", errors="ignore")


def _download_pdf(service, file_id: str) -> str:
    from pypdf import PdfReader
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    reader = PdfReader(io.BytesIO(buf.getvalue()))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def fetch_drive_files(
    folder_id: str | None = None,
    file_ids: list[str] | None = None,
    credentials_path: str | None = None,
    limit: int = 10,
) -> tuple[list[SourceDocument], dict[str, Any]]:
    """Retourne (documents, info_mode)."""
    cred = _credentials_path(credentials_path)
    if _real_available(cred):
        try:
            service = _build_service(cred)  # type: ignore[arg-type]
            query = "trashed=false and (mimeType='application/vnd.google-apps.document' " \
                    "or mimeType='text/plain' or mimeType='application/pdf')"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            files: list[dict] = []
            if file_ids:
                for fid in file_ids:
                    files.append(
                        service.files()
                        .get(fileId=fid, fields="id,name,mimeType,webViewLink")
                        .execute()
                    )
            else:
                resp = (
                    service.files()
                    .list(q=query, pageSize=max(1, limit), fields="files(id,name,mimeType,webViewLink)")
                    .execute()
                )
                files = resp.get("files", [])
            docs: list[SourceDocument] = []
            for f in files:
                mime = f.get("mimeType", "")
                if mime == "application/vnd.google-apps.document":
                    text = _export_google_doc(service, f["id"])
                elif mime == "application/pdf":
                    text = _download_pdf(service, f["id"])
                else:
                    text = _download_text_file(service, f["id"])
                docs.append(
                    SourceDocument(
                        id=f["id"],
                        name=f.get("name", f["id"]),
                        text=text,
                        source="drive",
                        url=f.get("webViewLink"),
                        metadata={"mimeType": mime, "folderId": folder_id},
                    )
                )
            return docs, {"mode": "live", "credentials": str(cred)}
        except Exception as exc:  # pragma: no cover - dépend de l'extérieur
            return _demo(folder_id, {"mode": "fallback", "error": str(exc)})
    return _demo(folder_id, {"mode": "demo", "reason": "credentials ou libs Google absentes"})


def _demo(folder_id: str | None, info: dict[str, Any]) -> tuple[list[SourceDocument], dict[str, Any]]:
    docs = [
        SourceDocument(
            id=d["id"],
            name=d["name"],
            text=d["text"],
            source="drive",
            url=f"https://drive.google.com/file/d/{d['id']}/view",
            metadata={"folderId": folder_id or "demo-folder", "demo": True},
        )
        for d in DEMO_DOCS
    ]
    return docs, info
