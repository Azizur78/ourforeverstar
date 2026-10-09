# ourforeverstar: V1 Website & Registry System

Premium celestial-gifting website plus a registry system. Customers reach the main site (via QR / NFC / link), choose
**Verify Registry**, enter a Registry Number and Registry Code, and view their registry. Staff manage registries in a
protected admin portal. Orders happen through Instagram; there is no e-commerce.

```
React (Vite)  ->  FastAPI  ->  SQLite
```

This repository runs **locally only**. Nothing is deployed to AWS.

## Structure

```
backend/    FastAPI app (app/), tests (tests/), uploads/ and data/ (git-ignored)
frontend/   React + Vite site and admin portal
scripts/    hash_password.py, seed_dev.py, import_registries.py (one-time migration)
.env.example  documented configuration (copy to .env)
```

## Run locally

Requires Python 3.11+ and Node 20+.

```bash
# 1. Configuration (from the project root)
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into SECRET_KEY in .env

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cd ..
python scripts/hash_password.py   # paste the printed ADMIN_PASSWORD_HASH line into .env
cd backend
uvicorn app.main:app --reload     # http://127.0.0.1:8000  (API docs: /api/docs in development)

# 3. Frontend (second terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173  (proxies /api to port 8000)
```

Optional development data (clearly fake `DEV-` records):

```bash
python scripts/seed_dev.py        # then verify with DEV-2026-000001 / DEMO-CODE-0001
```

Admin portal: http://localhost:5173/admin (username and password hash come from `.env`).

### Tests and build

```bash
cd backend && pytest              # backend tests (verification, admin, certificates, import script)
cd frontend && npm run build      # production bundle in frontend/dist
```

## Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `APP_ENV` | `development` or `production` (production: Secure cookies, API docs off) |
| `DATABASE_URL` | `sqlite:///./data/forever_star.db` (relative to `backend/`) |
| `SECRET_KEY` | **Required**, 32+ chars. Signs sessions and protects Registry Codes. Back it up: changing it makes stored codes unreadable |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` | Admin login. Generate the hash with `scripts/hash_password.py` |
| `UPLOAD_DIR` | Certificate storage folder (relative to `backend/`) |
| `MAX_CERTIFICATE_MB` | Upload size limit (default 5) |
| `INSTAGRAM_URL` | Used by every "Dedicate a Star" / contact button. Baked in at frontend build time |
| `CORS_ORIGINS` | Origins allowed to call the API with cookies |
| `TRUST_PROXY` | `true` only behind Nginx, so rate limiting sees real client IPs |

## How it works

**Customer flow.** `/verify` posts the number and code to `POST /api/registries/verify`. On success the server sets a
signed, HttpOnly, one-hour cookie bound to that registry's random `public_id`, and the browser opens
`/registry/{public_id}`. The registry and certificate endpoints require that cookie, so a copied URL alone reveals
nothing. Failures always return the same message, whether the number or the code was wrong or the registry is inactive.
Failed attempts are limited to 10 per 15 minutes per IP.

**Registry Codes.** Stored as an HMAC (verification and exact-match admin search) plus an encrypted copy so they can be
displayed to the verified customer and to admins. Never plaintext. Codes are case-insensitive.

**Admin.** scrypt password hash, signed HttpOnly SameSite=Strict session cookie (8 h), login rate-limited.
The developer sets the *initial* password via `ADMIN_PASSWORD_HASH` (`scripts/hash_password.py`). The admin can then use
**Admin > Change password**: the backend verifies the current password, validates the new one (10-128 characters, must match
the confirmation and differ from the current one), and stores only a new scrypt hash in the `admin_credentials` table, which
from then on overrides the `.env` value. The current session stays signed in; every other session is signed out (sessions are
bound to the password hash). Wrong-current-password attempts are rate limited. If the password is ever lost, the developer runs
`python scripts/reset_admin_password.py` (set a new one) or `--initial` (go back to the `.env` hash).
`DELETE /api/admin/registries/{id}` deactivates; registries are never hard-deleted in V1.

**Registry document.** Alongside the certificate, an admin can attach a registry document (PDF, PNG or JPG, same checks and storage as
certificates) to each registry, in the Add form (per record) or the Edit form. A verified customer sees a "Registry" tab with View and
Download buttons only when one exists. Existing databases gain the new `registry_document_path` column automatically at startup.

**Certificates.** PDF, PNG or JPG, up to 5 MB. Validated by extension and file signature, saved under a server-generated
name in `backend/uploads/certificates/`. Only the relative path is stored in SQLite. Files are not publicly served and
are streamed only to a verified customer or an admin. Storage sits behind a small interface
(`services/certificates.py`) so S3 can replace it later.

### API summary

Public: `POST /api/registries/verify`, `GET /api/registries/{public_id}`, `GET /api/registries/{public_id}/certificate`,
`GET /api/registries/{public_id}/registry-document`.
Admin (session required): `POST /api/admin/login|logout`, `GET /api/admin/me|stats`,
`GET|POST /api/admin/registries`, `GET|PUT|DELETE /api/admin/registries/{id}`, `PATCH .../status`,
`POST|GET .../certificate`, `POST|GET .../registry-document`, `POST .../registries/batch`. Error bodies are `{"message": ...}` with optional `errors` / `field`; no stack traces.

## One-time migration of the existing ~40 customers

Not part of the admin portal. When you have the CSV/XLSX:

```bash
python scripts/import_registries.py customers.xlsx                  # dry run: validates, writes nothing
python scripts/import_registries.py customers.xlsx --commit         # imports valid rows
python scripts/import_registries.py customers.xlsx --commit --strict  # imports nothing if any row is bad
```

Required columns: `registry_number, registry_code, dedicated_to, dedicated_by, dedication_date`. Optional: `occasion,
star_catalogue, constellation, distance, dedication_message, status`. Dates must match `--date-format`
(default `%Y-%m-%d`; for `31/12/2026` pass `--date-format %d/%m/%Y`); dates are never guessed. Duplicates within the file
(all copies are refused) or already in the database are reported, not overwritten. Certificates are uploaded afterwards
in the admin portal. Real data files are git-ignored. **No real data has been imported.**

## Future production deployment (not done)

Planned low-cost target: one AWS Lightsail instance, Nginx serving `frontend/dist` and proxying `/api` to
`uvicorn` (single worker, because the rate limiter is in-process), SQLite on disk. Checklist for that phase:
`APP_ENV=production`, HTTPS, `TRUST_PROXY=true`, Nginx `client_max_body_size 6m`, a systemd unit for uvicorn, real
domain in `sitemap.xml` / `robots.txt`, and scheduled backups of `backend/data/` (use `sqlite3 .backup`),
`backend/uploads/` and the `SECRET_KEY`.

## Render staging (Free plan)

**Shape:** one Render **Docker web service** (`Dockerfile`, `render.yaml`). The image builds the React app, then FastAPI serves
both the site (`https://<name>.onrender.com/`) and the API (`/api/...`) from the same origin, so the admin and registry
cookies work unchanged and there is no CORS or second domain. A Static Site + separate API was rejected: it would split the
origin and need rewrite rules for the cookies.

### Persistence: read this first
Render Free has an **ephemeral filesystem**: the SQLite database and uploaded certificates are **wiped on every redeploy,
restart and spin-down** (the service sleeps after 15 idle minutes and takes about a minute to wake). There are no persistent
disks on Free. So staging does not "keep" data; it **re-creates the existing test data on every start**:

| What | How it survives a redeploy |
|---|---|
| The 4 existing test records and the test certificate | Restored on startup from a Render **secret file** (`staging_seed.json`, produced locally by `scripts/export_staging_bundle.py`). Only missing records are inserted; nothing is overwritten. |
| Admin credential | `ADMIN_PASSWORD_HASH` / `ADMIN_USERNAME` env vars. The database is empty after a restart, so the env hash is the active credential every time. |
| Registry codes | Re-hashed/encrypted with the staging `SECRET_KEY` as they are restored, so staging does not need your local key. |
| Anything the owner adds or edits during testing (records, status changes, uploads, a changed password) | **Lost** on the next restart, redeploy or spin-down. Tell the owner. |

To change the staging admin credential permanently, update the `ADMIN_PASSWORD_HASH` env var (run the export script again);
a password changed through the Admin UI on staging only lasts until the next restart.

### Set-up (nothing here deploys by itself)
1. Locally: `python scripts/export_staging_bundle.py`. It reads (a copy of) your local database and writes the git-ignored
   `staging-bundle/` folder: `staging_seed.json`, `staging_seed.b64.txt`, `ADMIN_USERNAME.txt`, `ADMIN_PASSWORD_HASH.txt`.
   It prints counts only, never secrets, and changes nothing.
2. Push the repository to GitHub (a **private** repo is recommended). `.env` and `staging-bundle/` are git-ignored.
3. Render: New > Blueprint (uses `render.yaml`) or New > Web Service > Docker, plan **Free**, health check `/api/health`.
4. Environment variables (secrets are typed into Render, never into the repo):

| Variable | Value |
|---|---|
| `APP_ENV` | `production` (Secure cookies; Render terminates HTTPS) |
| `SECRET_KEY` | generated by Render (`generateValue`) |
| `ADMIN_USERNAME` | contents of `ADMIN_USERNAME.txt` |
| `ADMIN_PASSWORD_HASH` | contents of `ADMIN_PASSWORD_HASH.txt` (your current hash; the plaintext password is never needed) |
| `INSTAGRAM_URL` | public Instagram URL (baked into the frontend at build time, so changing it needs a redeploy) |
| `STAGING_SEED_FILE` | `/etc/secrets/staging_seed.json` |
| `TRUST_PROXY` | `true` |
| `CLIENT_IP_HEADER` | `CF-Connecting-IP` (Cloudflare overwrites it; `X-Forwarded-For` is client-spoofable on Render) |
| `NOINDEX` | `true` (adds `X-Robots-Tag: noindex` and serves a Disallow-all `robots.txt`) |
| `MAX_CERTIFICATE_MB` | `5` |
| `DATABASE_URL`, `UPLOAD_DIR`, `FRONTEND_DIST`, `PORT` | already set by the image / Render; leave alone |
| `CORS_ORIGINS` | not needed (same origin) |

5. Render > Environment > **Secret Files** > add `staging_seed.json` with the contents of the local file. (If Secret Files are
   not offered on your plan, instead set `STAGING_SEED_B64` to the contents of `staging_seed.b64.txt` and remove `STAGING_SEED_FILE`.)
6. Deploy. The log must contain `Staging seed applied: 4 record(s) added`. If the seed is configured but broken, the service
   refuses to start and says why (without printing any record values).

Build/start (already in the `Dockerfile`): `npm ci && npm run build` for the frontend, then
`uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1` from `backend/`.

### Test accounts and records (existing data only)
`DEV-2026-000001` and `-000002` active; `-000003` inactive; `-000099` inactive and holding the test certificate (view it
through Admin > Registries > View; to see it as a customer, activate that record first). Codes are in your local
`staging-bundle/staging_seed.json`, not in the repository.

### After the first deploy, check
Verify an active record, a wrong code and an inactive record; log in to the Admin; open the certificate preview. Then, from two
different devices or networks, make a few wrong attempts from one and confirm the other is not blocked (this confirms the rate
limiter sees real client IPs through `CF-Connecting-IP`).

## Known limitations / future work

- Rate limiting is in-memory (resets on restart; single process only).
- Registry access lasts 1 hour per verification; customers re-verify afterwards.
- About page copy and the sitemap domain are placeholders. No Open Graph image yet.
- Wallet, Transfer Certificate and similar features are "Coming Soon" in the FAQ only.
- The registry heading reads "For {Dedicated To} and {Dedicated By}". `/verify` opens the Verify Registry modal over the home page (so QR/NFC links keep working); the modal lives in `frontend/src/components/VerifyModal.jsx`, and the logo in `frontend/src/assets/ourforeverstar-logo.jpg`.
- Frontend has no automated tests; it was checked with a scripted browser run plus the production build.
