# Vanguard

**Evidence-led vendor and supply disruption intelligence with human-reviewed decisions.**

Vanguard brings supplier signals into one triage queue. Every incident links back to its source, separates reported facts from estimated impact, calls out what still needs verification, and records analyst decisions in an audit trail.

> The included dataset is synthetic. The example source URLs use `example.com` and are placeholders, not live news. Risk scores are transparent demo heuristics, not forecasts or confirmed financial loss.

## First-release workflow

1. Review the highest-priority vendor signals and risk score.
2. Open a signal to inspect dated source evidence, reported facts, inferred exposure, and verification steps.
3. Record a rationale to mark it relevant, reviewed, or dismissed.
4. Inspect the audit trail to see who changed the triage status and why.

The current release uses a small synthetic feed for four vendors. It does not connect to live news, ERP, shipment, email, contract, or LLM services and it does not send messages or execute procurement actions.

## Run locally

Requires Python 3.12 or newer.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Interactive API docs are at `/docs`.

The default bearer token `local-demo-token` is only for a local demo. Before deployment set `VANGUARD_API_TOKEN` to a unique random value, restrict network access, and use an identity provider and managed secret store. The sample UI will ask for the configured token if the local demo token is not active. Do not commit `.env`, database files, or real supplier records.

## API

Protected endpoints require `Authorization: Bearer <token>` and `X-User-Id: <analyst-id>`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/incidents` | Prioritized signal queue; optional `?status=new` filter |
| GET | `/api/incidents/{id}` | Incident with cited evidence and verification needs |
| PATCH | `/api/incidents/{id}/status` | Human triage update with a required rationale |
| GET | `/api/audit` | Recent review history; optional `?incident_id=...` |
| GET | `/api/vendors` | Synthetic monitored vendor list |

## Risk score

The demo score combines the strongest source severity, vendor criticality, and open-order exposure into a bounded 0–99 prioritization score. It is not a probability. Confidence is the mean confidence attached to the evidence records. These values are displayed separately and the interface labels exposure as context, not realized loss.

## Quality and security

CI checks run on pull requests to `dev` and `main`: Ruff linting, pytest, Bandit, pip-audit, and Gitleaks. Dependabot checks Python and GitHub Actions dependencies. Tests cover authentication, evidence visibility, rationale validation, incident status updates, audit recording, and risk ordering.

All source text is treated as data; this MVP has no model or tool execution. API writes are constrained to a fixed status enum, rationale strings are length-validated, SQL values are parameterized, and audit history is append-only through the API. This local-demo token model is not production authentication.

## Development conventions

- Branches: `main` (stable) and `dev` (integration).
- Feature/fix branches use conventional prefixes, e.g. `feat/live-source-connectors`, `fix/audit-pagination`.
- Commit subjects use Conventional Commits: `feat: add source freshness indicator`, `fix: reject invalid status transitions`.
- Open a PR to `dev`; changes intended for release move from `dev` to `main` through a PR after CI passes and review is complete.
