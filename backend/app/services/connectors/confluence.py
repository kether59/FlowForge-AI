"""Connecteur Confluence Atlassian (REST API v2).

Utilise l'authentification Basic (email + API token). Si aucune configuration
n'est fournie, un jeu de pages de démonstration est renvoyé.
"""

from __future__ import annotations

import base64
import html
import re
from typing import Any

import httpx

from app.config import get_settings
from app.schemas import SourceDocument

DEMO_PAGES = [
    {
        "id": "conf-demo-archi",
        "title": "Architecture plateforme — vue d'ensemble",
        "body": (
            "La plateforme s'articule autour d'un orchestrateur asynchrone (FastAPI) et d'un "
            "moteur d'exécution de graphes. Chaque nœud est un worker asynchrone idempotent. "
            "Les exécutions sont diffusées en temps réel via WebSocket. Le stockage vectoriel "
            "est abstrait derrière une interface unique (cosine similarity en prototype, "
            "pgvector ou Qdrant en production).\n\n"
            "Les secrets sont injectés par variables d'environnement et jamais persistés dans "
            "les définitions de workflow."
        ),
    },
    {
        "id": "conf-demo-runbook",
        "title": "Runbook — incidents P1",
        "body": (
            "1. Ouvrir un canal d'incident et nommer un incident commander.\n"
            "2. Vérifier les dashboards de latence et le taux d'erreur des nœuds LLM.\n"
            "3. Si le provider principal est indisponible, basculer sur le provider secondaire "
            "via le nœud Routeur (fallback).\n"
            "4. Communiquer toutes les 30 minutes.\n"
            "5. Rédiger le post-mortem sous 5 jours."
        ),
    },
    {
        "id": "conf-demo-rag",
        "title": "Bonnes pratiques RAG",
        "body": (
            "Choisir des chunks de 500 à 1000 caractères avec 10 à 20% de recouvrement. "
            "Conserver les métadonnées (source, section, date) pour citer les passages. "
            "Évaluer le retrieval avec un jeu de questions annotées (hit rate@k, MRR). "
            "Ne jamais injecter plus de contexte que nécessaire : préférer 4 à 6 chunks "
            "et un re-ranking. Toujours prévoir une réponse de repli lorsque le score "
            "de similarité est trop faible."
        ),
    },
]


def _strip_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"</(p|div|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", text)).strip()


def _config(explicit: dict[str, str | None]) -> tuple[str | None, str | None, str | None]:
    s = get_settings()
    return (
        (explicit.get("baseUrl") or s.confluence_base_url),
        (explicit.get("email") or s.confluence_email),
        (explicit.get("apiToken") or s.confluence_api_token),
    )


def fetch_confluence_pages(
    base_url: str | None = None,
    email: str | None = None,
    api_token: str | None = None,
    page_id: str | None = None,
    space_key: str | None = None,
    cql: str | None = None,
    limit: int = 10,
) -> tuple[list[SourceDocument], dict[str, Any]]:
    base, mail, token = _config({"baseUrl": base_url, "email": email, "apiToken": api_token})
    if not (base and mail and token):
        return _demo(space_key, {"mode": "demo", "reason": "CONFLUENCE_* non configurés"})

    auth = base64.b64encode(f"{mail}:{token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    root = base.rstrip("/") + "/wiki/api/v2"

    try:
        with httpx.Client(timeout=30, headers=headers) as client:
            pages: list[dict[str, Any]] = []
            if page_id:
                r = client.get(f"{root}/pages/{page_id}", params={"body-format": "storage"})
                r.raise_for_status()
                pages = [r.json()]
            elif cql:
                r = client.get(
                    f"{base.rstrip('/')}/wiki/rest/api/search",
                    params={"cql": cql, "limit": limit, "expand": "content.body.storage"},
                )
                r.raise_for_status()
                for item in r.json().get("results", [])[:limit]:
                    content = item.get("content", {})
                    pages.append(
                        {
                            "id": content.get("id", item.get("id")),
                            "title": content.get("title") or item.get("title"),
                            "body": {"storage": {"value": item.get("body", {}).get("storage", {}).get("value", "")}},
                            "_links": content.get("_links", {}),
                        }
                    )
            else:
                params: dict[str, Any] = {"body-format": "storage", "limit": limit}
                if space_key:
                    params["space-id"] = space_key
                r = client.get(f"{root}/pages", params=params)
                r.raise_for_status()
                pages = r.json().get("results", [])[:limit]

            docs = [
                SourceDocument(
                    id=str(p.get("id")),
                    name=p.get("title", f"page-{p.get('id')}"),
                    text=_strip_html(
                        (p.get("body", {}).get("storage", {}) or {}).get("value", "")
                        or (p.get("body", {}).get("view", {}) or {}).get("value", "")
                    ),
                    source="confluence",
                    url=(p.get("_links", {}) or {}).get("webui", base),
                    metadata={"spaceKey": space_key, "pageId": p.get("id")},
                )
                for p in pages
            ]
            return docs, {"mode": "live", "baseUrl": base, "count": len(docs)}
    except Exception as exc:  # pragma: no cover
        return _demo(space_key, {"mode": "fallback", "error": str(exc)})


def _demo(space_key: str | None, info: dict[str, Any]) -> tuple[list[SourceDocument], dict[str, Any]]:
    docs = [
        SourceDocument(
            id=p["id"],
            name=p["title"],
            text=p["body"],
            source="confluence",
            url=f"https://demo.atlassian.net/wiki/spaces/{space_key or 'DEMO'}/pages/{p['id']}",
            metadata={"spaceKey": space_key or "DEMO", "demo": True},
        )
        for p in DEMO_PAGES
    ]
    return docs, info
