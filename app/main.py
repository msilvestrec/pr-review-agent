import logging
import os

import anthropic
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from app.agent import run_review
from app.github_client import GitHubClient
from app.security import verify_signature

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pr-review-agent")

app = FastAPI(title="PR Review Agent")

HANDLED_ACTIONS = {"opened", "synchronize", "reopened"}


def review_and_comment(repo: str, pr_number: int) -> None:
    """Corre en segundo plano: GitHub necesita respuesta rápida al webhook."""
    try:
        github = GitHubClient(os.environ["GITHUB_TOKEN"])
        llm = anthropic.Anthropic()
        review = run_review(llm, github, repo, pr_number)
        github.post_comment(repo, pr_number, review)
        log.info("Revisión publicada en %s#%s", repo, pr_number)
    except Exception:
        log.exception("Falló la revisión de %s#%s", repo, pr_number)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks):
    body = await request.body()
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret or not verify_signature(secret, body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401, detail="Firma inválida")

    if request.headers.get("X-GitHub-Event") != "pull_request":
        return {"status": "ignored"}

    payload = await request.json()
    if payload.get("action") not in HANDLED_ACTIONS:
        return {"status": "ignored"}

    repo = payload["repository"]["full_name"]
    number = payload["pull_request"]["number"]
    background.add_task(review_and_comment, repo, number)
    return {"status": "queued"}
