# PR Review Agent

An AI agent that reviews GitHub pull requests. When a PR is opened or updated, GitHub notifies the service through a webhook, and a Claude-powered agent reads the diff, explores the repository with tools to understand the context, and posts a concise review as a comment on the PR.

It is built as a small, testable FastAPI service with an explicit agent loop (no agent framework), so every step of the reasoning is visible in the code.

## How it works

```
GitHub PR event ──► POST /webhook ──► verify HMAC signature ──► queue background task
                                                                      │
                                      ┌───────────────────────────────┘
                                      ▼
                              Agent loop (Claude + tool calling)
                                │   ▲
                 tool_use ──────┘   └────── tool_result
                 search_code / read_file (GitHub API)
                                      │
                                      ▼
                         Review posted as a PR comment
```

1. **Webhook** (`app/main.py`): receives the GitHub event, rejects anything without a valid signature, and ignores events that are not `opened`, `synchronize` or `reopened` on a pull request. The review runs in the background so GitHub gets an immediate response.
2. **Agent loop** (`app/agent.py`): sends Claude the PR diff and two tools, `search_code` and `read_file`. Claude decides which tools to call (for example, to see where a changed function is used) and keeps going until it produces the final review.
3. **GitHub client** (`app/github_client.py`): a thin wrapper over the GitHub REST API. Each method is one capability of the agent.
4. **Signature check** (`app/security.py`): validates `X-Hub-Signature-256` with HMAC-SHA256 and a constant-time comparison.

## Safety controls

- **Authenticated webhook:** requests with a missing or invalid signature get a `401`.
- **Step limit:** the agent loop stops after `AGENT_MAX_STEPS` iterations, so it cannot loop forever or run up costs.
- **Tool errors do not crash the agent:** if a tool fails (rate limit, missing file), the error goes back to the model so it can adapt.
- **Bounded context:** the diff and every tool result are truncated to a fixed size.
- **Review quality prompt:** the model is told to report only concrete, verifiable problems (bugs, edge cases, missing tests, security risks) and to skip style comments.

## Tests

The suite (12 tests) runs without network access or an API key: the LLM and the GitHub client are replaced by scripted fakes.

- Agent: tool use followed by a final answer, tool errors returned to the model, step limit.
- Security: valid signature, wrong secret, missing header, malformed header.
- Webhook: health check, PR queued, bad signature rejected, ignored actions and events.

```bash
pip install -r requirements-dev.txt
pytest
```

CI runs the tests and builds the Docker image on every push and pull request (`.github/workflows/ci.yml`).

## Run it locally

```bash
cp .env.example .env        # fill in the values
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --port 8000
```

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `GITHUB_TOKEN` | Token with read access to the repo and permission to comment on PRs |
| `WEBHOOK_SECRET` | Shared secret configured in the GitHub webhook |
| `ANTHROPIC_MODEL` | Optional, model name |
| `AGENT_MAX_STEPS` | Optional, maximum agent iterations (default 8) |

To receive real events, expose the service with a tunnel (for example `ngrok http 8000`) and add a webhook in your repository settings: payload URL `https://<your-url>/webhook`, content type `application/json`, the same secret as `WEBHOOK_SECRET`, and the **Pull requests** event.

## Docker

```bash
docker build -t pr-review-agent .
docker run --env-file .env -p 8000:8000 pr-review-agent
```

The image is a standard container listening on port 8000, so it can run on any container platform.

## Roadmap

- Deploy to AWS (container service) with a CD step in GitHub Actions.
- Post line-level review comments instead of a single summary comment.
- Skip PRs from bots and very large diffs explicitly.

## Stack

Python 3.12 · FastAPI · Anthropic API (tool calling) · httpx · pytest · Docker · GitHub Actions
