import base64

import httpx

API = "https://api.github.com"
MAX_CHARS = 8000  # tope por resultado de tool para no inflar el contexto


def _cut(text: str, limit: int = MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[recortado, {len(text) - limit} caracteres más]"


class GitHubClient:
    """Cliente mínimo de la API de GitHub. Cada método es una capacidad del agente."""

    def __init__(self, token: str, timeout: float = 20.0):
        self.http = httpx.Client(
            base_url=API,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        r = self.http.get(
            f"/repos/{repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        r.raise_for_status()
        return r.text

    def get_pr_head_sha(self, repo: str, pr_number: int) -> str:
        r = self.http.get(f"/repos/{repo}/pulls/{pr_number}")
        r.raise_for_status()
        return r.json()["head"]["sha"]

    def read_file(self, repo: str, path: str, ref: str) -> str:
        r = self.http.get(f"/repos/{repo}/contents/{path}", params={"ref": ref})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return "Eso es un directorio, contiene: " + ", ".join(i["name"] for i in data)
        return _cut(base64.b64decode(data["content"]).decode("utf-8", errors="replace"))

    def search_code(self, repo: str, query: str) -> str:
        r = self.http.get("/search/code", params={"q": f"{query} repo:{repo}", "per_page": 10})
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return "Sin resultados."
        return "\n".join(i["path"] for i in items)

    def post_comment(self, repo: str, pr_number: int, body: str) -> None:
        r = self.http.post(f"/repos/{repo}/issues/{pr_number}/comments", json={"body": body})
        r.raise_for_status()
