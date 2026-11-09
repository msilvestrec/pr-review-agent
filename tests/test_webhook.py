import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app import main

SECRET = "s3cret"


def post(client, payload: dict, event="pull_request", secret=SECRET):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": event},
    )


def make_client(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", SECRET)
    calls = []
    monkeypatch.setattr(main, "review_and_comment", lambda repo, n: calls.append((repo, n)))
    return TestClient(main.app), calls


PR = {"action": "opened", "repository": {"full_name": "org/repo"}, "pull_request": {"number": 7}}


def test_health(monkeypatch):
    client, _ = make_client(monkeypatch)
    assert client.get("/health").json() == {"status": "ok"}


def test_pr_abierta_encola_revision(monkeypatch):
    client, calls = make_client(monkeypatch)
    r = post(client, PR)
    assert r.json() == {"status": "queued"}
    assert calls == [("org/repo", 7)]


def test_firma_mala_devuelve_401(monkeypatch):
    client, calls = make_client(monkeypatch)
    assert post(client, PR, secret="otro").status_code == 401
    assert calls == []


def test_accion_ignorada(monkeypatch):
    client, calls = make_client(monkeypatch)
    assert post(client, {**PR, "action": "closed"}).json() == {"status": "ignored"}
    assert calls == []


def test_evento_ignorado(monkeypatch):
    client, calls = make_client(monkeypatch)
    assert post(client, PR, event="push").json() == {"status": "ignored"}
    assert calls == []
