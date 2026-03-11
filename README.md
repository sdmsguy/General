# Service Desk Co-Pilot Agent

A lightweight Python app that lets users:
1. Describe an issue and attach a screenshot.
2. Receive top matching troubleshooting suggestions from HALO-style KB articles.
3. Create a HALO ticket if suggestions did not solve the issue.

## Run locally

```bash
python copilot_service_desk_app.py
```

Then open `http://localhost:8000`.

## HALO integration

Set environment variables for live ticket creation:

- `HALO_BASE_URL`
- `HALO_CLIENT_ID`
- `HALO_CLIENT_SECRET`
- `HALO_TENANT`

If these are not set, the app returns a dry-run ticket preview.

## Test

```bash
pytest -q
```
