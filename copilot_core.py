import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HaloConfig:
    base_url: str
    client_id: str
    client_secret: str
    tenant: str

    @classmethod
    def from_env(cls) -> "HaloConfig | None":
        base_url = os.getenv("HALO_BASE_URL", "").strip()
        client_id = os.getenv("HALO_CLIENT_ID", "").strip()
        client_secret = os.getenv("HALO_CLIENT_SECRET", "").strip()
        tenant = os.getenv("HALO_TENANT", "").strip()
        if not all([base_url, client_id, client_secret, tenant]):
            return None
        return cls(base_url=base_url, client_id=client_id, client_secret=client_secret, tenant=tenant)


class KBSuggester:
    def __init__(self, kb_file: Path):
        self.articles = json.loads(kb_file.read_text(encoding="utf-8"))

    def suggest(self, issue: str, max_results: int = 3) -> list[dict[str, Any]]:
        issue_words = set(issue.lower().split())
        scored: list[tuple[int, dict[str, Any]]] = []
        for article in self.articles:
            terms = set(" ".join(article["keywords"]).lower().split())
            score = len(issue_words.intersection(terms))
            scored.append((score, article))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [article for score, article in scored if score > 0][:max_results]


class HaloClient:
    def __init__(self, config: HaloConfig):
        self.config = config

    def _token(self) -> str:
        import requests

        token_url = f"{self.config.base_url.rstrip('/')}/auth/token"
        response = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": "all",
                "tenant": self.config.tenant,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def create_ticket(self, summary: str, details: str, screenshot_path: str | None = None) -> dict[str, Any]:
        import requests

        token = self._token()
        ticket_url = f"{self.config.base_url.rstrip('/')}/api/tickets"
        payload = {
            "summary": summary,
            "details": details,
            "source": "CopilotAgent",
            "priority": "Medium",
        }
        if screenshot_path:
            payload["attachments"] = [{"fileName": Path(screenshot_path).name}]

        response = requests.post(
            ticket_url,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
