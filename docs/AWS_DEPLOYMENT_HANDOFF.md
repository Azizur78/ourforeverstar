# OurForeverStar — AWS deployment handoff

Audience: the engineer deploying to AWS. Written from the actual code at commit `1de7f21` (branch `staging`).
Contains variable NAMES only. Never paste secret values into Git, tickets or chat; hand them over through a password manager or AWS Secrets Manager / SSM Parameter Store.

> "Verified" below means read from code or run locally (Docker Desktop on Windows, bind mounts). **Nothing has been run on AWS.** Commands in sections 4, 6 and 7 are standard Linux/Docker/Caddy/Nginx practice and have **not** been tested on an EC2 instance; test them on a throw-away instance first. Section 12 lists what must be proven on the real host.

## 0. Security rules (read first)

- **Never use the AWS root account** for deployment or day-to-day work, and never create root access keys. Keep the root user for billing/account recovery only, protected by MFA and a unique password.
- Deploy with an **IAM Identity Center user or an IAM user with MFA** and least privilege (EC2, EBS, security groups for this one project; plus S3/IAM-role permissions only if the S3 option is used).
- The application reaches AWS (S3 option only) through an **EC2 instance role**. Do not create access keys for the app and do not put `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in the env file, in Git or in chat.
- Never commit or paste: `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `SMTP_PASSWORD`, the env file, `.env`, `staging-bundle/`, database files, uploads.
- Require IMDSv2 on the instance (instance metadata option "V2 only") and keep SSH closed to the world: allow port 22 only from the administrator's IP, or use SSM Session Manager and open no port 22. (AWS console settings; confirm the current option names in the console.)
- Turn on a billing budget/alert before creating anything (section 11).

## 1. What the app is

One container serves everything on one origin: React (built into the image) + FastAPI under `/api`. State is:

| State | Where | Notes |
|---|---|---|
| Records, admin password override, recovery requests, customer emails | one SQLite file, WAL mode | `DATABASE_URL` (image default `sqlite:////app/backend/data/forever_star.db`) |
| Customer PDFs | files under `UPLOAD_DIR/certificates/<32hex>.pdf` (image default `/app/backend/uploads`) **or** a private S3 bucket | DB stores only the key |
| Configuration | environment variables | no settings table |

The container filesystem is disposable. Anything not on a mounted volume (or S3) is lost when the container is recreated.

## 2. Architecture (smallest design that matches the code)

One EC2 instance, Docker, one EBS data volume mounted on the host, and a TLS reverse proxy (Caddy or Nginx) in front.

- **Exactly one container, one worker** (in-memory rate limiter + SQLite writer). Do not add autoscaling or replicas. The Dockerfile already uses `--workers 1`.
- SQLite must live on a **local block device (EBS)**, not EFS/NFS (WAL needs shared-memory locking).
- The proxy terminates HTTPS and forwards to `127.0.0.1:10000`. Publish the container port on loopback only (`-p 127.0.0.1:10000:10000`), otherwise clients could reach the app directly and spoof their IP (`TRUST_PROXY=true` trusts the forwarded header).
- Security group: inbound 80 and 443 from anywhere; 22 only from the administrator's IP (or none with SSM). Nothing else. Outbound: HTTPS (image pulls, TLS certificate issuance, and S3/SMTP if used).
- Not needed: load balancer, NAT gateway, RDS, EFS, ECS.

### Storage choice (pick one)

- **Option L (local volume, default):** PDFs on the EBS volume next to the DB. One backup process covers both.
- **Option S (S3):** PDFs in a private bucket; the DB is still on EBS and must still be backed up. Adds PDF durability and an IAM role. Not enabled by default. A later switch is supported by `scripts/migrate_documents_to_s3.py` (section 8).

Both are covered by automated tests (S3 against `moto`, not real AWS).

## 3. Prepare the instance

1. Install Docker Engine from Docker's official instructions for the chosen OS image, and enable it at boot.
2. Clone the repository (the `main` branch once it exists) and build:
   ```bash
   docker build -t ourforeverstar --build-arg INSTAGRAM_URL=https://www.instagram.com/<handle>/ .
   ```
   `INSTAGRAM_URL` is public and baked into the frontend; it is the only build arg.

## 4. Create, attach, format and mount the EBS data volume

Console/CLI steps (use your IAM user, not root):

1. Create an EBS volume **in the same Availability Zone as the instance**, with encryption enabled and a size that leaves room for the database plus all PDFs with growth (volumes can be enlarged later). Choose the volume type deliberately; check current EBS pricing and options yourself.
2. Attach it to the instance (e.g. as `/dev/sdf`). On current instance types it appears inside Linux as an NVMe device such as `/dev/nvme1n1`, not `/dev/sdf`.
3. On the instance:
   ```bash
   lsblk -f                      # find the NEW disk: it has no FSTYPE and no mountpoint
   ```
   **Format only a brand-new, empty disk.** Formatting destroys existing data. If `lsblk -f` already shows a filesystem on it (for example a volume restored from a snapshot), skip the `mkfs` line.
   ```bash
   sudo mkfs.ext4 -L ofsdata /dev/nvme1n1          # first time only; replace the device name
   sudo mkdir -p /srv/ofs
   sudo chattr +i /srv/ofs                         # while unmounted: writes fail if the volume is ever missing,
                                                   # so the app can never silently write to the root disk
   sudo blkid /dev/nvme1n1                         # note the UUID (do not use /dev names in fstab)
   sudo cp /etc/fstab /etc/fstab.bak
   echo 'UUID=<uuid-from-blkid>  /srv/ofs  ext4  defaults,nofail  0  2' | sudo tee -a /etc/fstab
   sudo mount -a                                   # test the entry NOW, before any reboot
   findmnt /srv/ofs                                # must show the new device
   ```
   If `mount -a` reports an error, restore `/etc/fstab.bak` before doing anything else. A bad fstab line can stop the instance from booting.
4. Create the directories, owned by the container user (UID 10001):
   ```bash
   sudo mkdir -p /srv/ofs/data /srv/ofs/uploads /srv/ofs/backups
   sudo chown -R 10001:10001 /srv/ofs/data /srv/ofs/uploads
   sudo chmod 700 /srv/ofs/backups
   ```
   `backups/` is host-only (never mounted into the container). Backups on the same volume do not protect against losing the volume: copy them off the instance (section 9).
5. Reboot once and confirm `findmnt /srv/ofs` still works **before** loading real data.
6. Check before every `docker run`: `findmnt /srv/ofs` succeeds.

## 5. Environment file and run command

Create `/etc/ofs/ofs.env` (see section 6 for contents):
```bash
sudo mkdir -p /etc/ofs
sudo install -m 600 -o root -g root /dev/null /etc/ofs/ofs.env
sudo nano /etc/ofs/ofs.env           # add values; never echo them into shell history
sudo ls -l /etc/ofs/ofs.env          # must show -rw------- root root
```
Format rules for Docker's `--env-file` (it is **not** a shell script):
- One `NAME=value` per line, no spaces around `=`.
- **No quotes** (quotes become part of the value), no `export`, no trailing spaces. Comment lines start with `#`.
- Values containing `:` (the scrypt hash) are fine unquoted.
- Prefer generating the file from Secrets Manager / SSM at deploy time over typing values on the server.

Run:
```bash
findmnt /srv/ofs && docker run -d --name ofs --restart unless-stopped \
  -p 127.0.0.1:10000:10000 \
  -v /srv/ofs/data:/app/backend/data \
  -v /srv/ofs/uploads:/app/backend/uploads \
  --env-file /etc/ofs/ofs.env \
  --health-cmd "python -c \"import urllib.request;urllib.request.urlopen('http://127.0.0.1:10000/api/health',timeout=3)\"" \
  --health-interval 30s --health-retries 3 \
  ourforeverstar
```
The image has no `curl`, and the Dockerfile defines no `HEALTHCHECK`, hence the Python one-liner (the container's Python 3.12 is present; port 10000 is the default `PORT`). `docker ps` then shows `healthy`. Check the endpoint from the host with `curl -s http://127.0.0.1:10000/api/health`.

## 6. Environment variables (extracted from `backend/app/config.py`, `Dockerfile`, `.env.example`, `render.yaml`)

### Always (both storage options)

| Variable | Status | Value / source |
|---|---|---|
| `APP_ENV` | **required: `production`** | **The Dockerfile does not set it.** If omitted it defaults to `development`: cookies lose the Secure flag and `/api/docs` is exposed. |
| `SECRET_KEY` | **required; reuse the owner's existing key** | Min 32 chars. If lost or changed, every registry code stops verifying (verified: 0 of 2 active records verified with a different key). Back it up separately from the database. |
| `ADMIN_USERNAME` | **required; reuse existing** (`admin` locally) | The DB password-override row is keyed by this name; a different value silently falls back to the env hash. |
| `ADMIN_PASSWORD_HASH` | recommended | Fallback only; the DB row (`admin_credentials`) overrides it. With neither, admin login is disabled. Format `scrypt:...`; generate with `scripts/hash_password.py`. Secret. |
| `TRUST_PROXY` | required behind a proxy | `true` (and only with the loopback binding above) |
| `CLIENT_IP_HEADER` | optional | default `x-forwarded-for` (the app trusts the **rightmost** entry). Use `CF-Connecting-IP` only behind Cloudflare. |
| `DATABASE_URL` | image default is correct | `sqlite:////app/backend/data/forever_star.db` (four slashes = absolute path). Only `sqlite:///` URLs are accepted. |
| `UPLOAD_DIR` | image default is correct | `/app/backend/uploads` |
| `MAX_CERTIFICATE_MB` | optional | default `5` |
| `FRONTEND_DIST` | set by the image | do not override |
| `PORT` | optional | default `10000`; if changed, update the proxy and health command |
| `NOINDEX` | **must be unset or `false` in production** | `true` adds `X-Robots-Tag: noindex` and serves a Disallow-all `robots.txt` |
| `CORS_ORIGINS` | not needed (same origin) | default allows `http://localhost:5173`; harmless, may be set to the real https origin |

### Option L: local volume
`STORAGE_BACKEND=local` (this is the default; no other storage variables).

### Option S: S3 (all conditional)
| Variable | Status |
|---|---|
| `STORAGE_BACKEND=s3` | required |
| `S3_BUCKET`, `S3_REGION` | required (startup fails without them) |
| `S3_PREFIX` | optional (folder in the bucket) |
| `S3_ENDPOINT_URL` | leave unset for AWS |
| `DOWNLOAD_URL_TTL_SECONDS` | optional, 60-900, default 300 |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | **do not set**; attach an instance role (boto3 uses it automatically) |

Instance-role policy on the bucket's objects: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`; optionally `s3:ListBucket` on the bucket (without it a missing object shows as 403, handled as "unavailable"). Bucket: Block Public Access on; default encryption SSE-S3 (the app uploads with `AES256`; a KMS-only bucket policy would reject uploads). Outbound HTTPS to S3.

### Optional email (recovery emails): set together
`SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `EMAIL_FROM`, `PUBLIC_BASE_URL` (public https URL, no trailing slash). Nothing is sent unless `SMTP_HOST` and `EMAIL_FROM` are set.

### Must NOT be present in production
`STAGING_SEED_FILE`, `STAGING_SEED_B64` (would re-insert missing demo/test records into the live DB), and `NOINDEX=true`. Verify absence:
```bash
sudo grep -c -E '^(STAGING_SEED_FILE|STAGING_SEED_B64)=' /etc/ofs/ofs.env     # must print 0
sudo grep -E '^NOINDEX=' /etc/ofs/ofs.env                                      # must print nothing, or NOINDEX=false
docker exec ofs python -c "import os;print([k for k in ('STAGING_SEED_FILE','STAGING_SEED_B64','NOINDEX') if os.environ.get(k)])"   # names only; expect []
```
(The last command prints only variable names that are set, never values.)

## 7. HTTPS reverse proxy (pick one; install per the official docs)

Prerequisites: a hostname whose DNS A record points at the instance's Elastic IP; ports 80 and 443 open. Production cookies are Secure, so **admin login only works over HTTPS** on the final hostname.

### Caddy (automatic certificates)
`/etc/caddy/Caddyfile` (replace the hostname):
```
ofs.example.com {
    encode gzip
    header Strict-Transport-Security "max-age=300"
    request_body {
        max_size 210MB
    }
    reverse_proxy 127.0.0.1:10000
}
```
### Nginx (+ certbot for certificates)
```
server {
    listen 443 ssl;
    server_name ofs.example.com;
    # ssl_certificate / ssl_certificate_key: as issued by certbot
    client_max_body_size 210m;
    add_header Strict-Transport-Security "max-age=300" always;
    location / {
        proxy_pass http://127.0.0.1:10000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
server { listen 80; server_name ofs.example.com; return 301 https://$host$request_uri; }
```
Notes:
- **Body limit:** a single PDF is capped at `MAX_CERTIFICATE_MB` (5) by the app. The batch endpoint accepts up to 20 certificates plus 20 registry documents: 20 x 5 MB x 2 + 1 MB, about 201 MB. The example 210 MB covers that. If you never need big batches, a smaller limit works, but not below about 6 MB or single uploads fail with 413.
- **HSTS:** start with a short `max-age=300` and raise it (e.g. to a year) only after everything works over HTTPS for a while. Do not add `includeSubDomains` or `preload` unless the whole domain is committed to HTTPS.
- **Client IP:** the app trusts the rightmost `X-Forwarded-For` entry. After deployment, prove it (section 10, step 9).
- Pre-cutover testing needs a real hostname with HTTPS (for example a temporary subdomain), because Secure cookies are not stored over plain `http://<ip>`. Adding that DNS record is the owner's decision.

## 8. Migrating the existing data (rehearse on a staging copy first)

1. Owner stops writing to the current system.
2. On the current machine, back up with the SQLite API, never a plain file copy (WAL):
   `python -c "import sqlite3;s=sqlite3.connect('backend/data/forever_star.db');d=sqlite3.connect('forever_star.backup.db');s.backup(d);d.close();s.close()"`
3. Transfer `forever_star.backup.db` and `backend/uploads/certificates/` securely (scp over SSH; they contain customer data).
4. On the server (container stopped): install the backup as `/srv/ofs/data/forever_star.db`, copy PDFs to `/srv/ofs/uploads/certificates/` keeping filenames identical, ensure no stale `forever_star.db-wal`/`-shm` exists, then `sudo chown -R 10001:10001 /srv/ofs/data /srv/ofs/uploads`.
5. Start with the **same** `SECRET_KEY` and `ADMIN_USERNAME`.
6. Run section 10. Only then change DNS (section 13).

Rollback: point DNS back to the old host (keep it intact). Records created on AWS after cutover must be exported first.

Option S migration of PDFs: `scripts/migrate_documents_to_s3.py` (dry run by default; `--commit` copies; never overwrites or deletes). It is **not in the Docker image** (`.dockerignore` excludes `scripts/`), so run it from a git checkout on the host in a venv (`pip install -r backend/requirements.txt`) with `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_REGION`, `DATABASE_URL=sqlite:////srv/ofs/data/forever_star.db` and `UPLOAD_DIR=/srv/ofs/uploads` exported. The same applies to `scripts/reset_admin_password.py` (run with the app stopped).

## 9. Backup and restore

The image has no `sqlite3` CLI, so use Python's online backup API. **Never back up by copying only `forever_star.db` while the app runs** (recent writes live in the `-wal` file).

### Backup (daily by cron, and before every upgrade)
`/usr/local/bin/ofs-backup.sh` (run as root):
```bash
#!/bin/sh
set -eu
STAMP=$(date +%F-%H%M)
DEST=/srv/ofs/backups
docker exec -i ofs python - <<'PY'
import sqlite3
s = sqlite3.connect('/app/backend/data/forever_star.db')
d = sqlite3.connect('/app/backend/data/_backup.tmp')
s.backup(d)
ok = d.execute('PRAGMA integrity_check').fetchone()[0]
d.close(); s.close()
assert ok == 'ok', ok
PY
mv /srv/ofs/data/_backup.tmp "$DEST/forever_star-$STAMP.db"
rm -f /srv/ofs/data/_backup.tmp-wal /srv/ofs/data/_backup.tmp-shm      # tidy leftovers
chmod 600 "$DEST/forever_star-$STAMP.db"
rsync -a /srv/ofs/uploads/ "$DEST/uploads/"        # Option L only (PDFs on the volume)
find "$DEST" -maxdepth 1 -name 'forever_star-*.db' -mtime +30 -delete    # keep ~30 days locally
```
Then **copy `$DEST` off the instance** to a separate location (another account/region, or a private backup bucket with a policy limited to the backup prefix; this AWS configuration is a suggestion and has not been tested). An EBS snapshot is an additional, crash-consistent safety net, not a replacement for the Python backup. Option S still needs the DB backup; consider bucket versioning for PDFs.

Separately and securely store `SECRET_KEY` (not in the same place as the database backups).

### Restore
```bash
docker stop ofs
sudo cp /srv/ofs/backups/forever_star-<stamp>.db /srv/ofs/data/forever_star.db
sudo rm -f /srv/ofs/data/forever_star.db-wal /srv/ofs/data/forever_star.db-shm   # stale journals from the old DB
sudo rsync -a /srv/ofs/backups/uploads/ /srv/ofs/uploads/                        # Option L only
sudo chown -R 10001:10001 /srv/ofs/data /srv/ofs/uploads
docker start ofs
```
Then run section 10. Do not restore over live data without first saving a fresh backup of the current state.

### Monthly restore test (a backup you have not restored is not a backup)
On a scratch directory, never the live one:
```bash
T=$(mktemp -d)
cp /srv/ofs/backups/forever_star-<latest>.db "$T/forever_star.db"
python3 - "$T/forever_star.db" <<'PY'
import sqlite3, sys, os
c = sqlite3.connect(sys.argv[1])
print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
for t in ('registries', 'admin_credentials', 'recovery_requests'):
    print(t, c.execute(f'select count(*) from {t}').fetchone()[0])
keys = [r[0] for col in ('certificate_path', 'registry_document_path')
        for r in c.execute(f"select {col} from registries where {col} is not null and {col} != ''")]
missing = [k for k in keys if not os.path.isfile(os.path.join('/srv/ofs/backups/uploads', k))]
print('referenced documents:', len(keys), 'missing from backup:', len(missing))   # Option L
PY
rm -rf "$T"
```
Expect `integrity: ok`, row counts matching production, and 0 missing. About quarterly, also start a scratch container from the backup on a loopback-only port with the same `SECRET_KEY` and confirm one known registry verifies. Do not point a scratch container at the live S3 prefix.

## 10. Post-deployment verification checklist

1. `curl -s https://<host>/api/health` returns `{"status":"ok"}`; `docker ps` shows `healthy`.
2. `https://<host>/api/docs` returns 404 (proves `APP_ENV=production`).
3. `findmnt /srv/ofs` shows the EBS device; `ls -ln /srv/ofs/data` shows owner 10001.
4. Section 6 absence checks pass (no `STAGING_SEED_*`, `NOINDEX` unset or false); response headers do **not** contain `X-Robots-Tag: noindex`.
5. Admin login with the existing credentials works (cookie flags: HttpOnly, Secure, SameSite=Strict).
6. Registry count and statuses match the pre-migration record.
7. As a customer, verify one known active registry; certificate View and Download work. An inactive registry is refused.
8. `docker restart ofs`, then `docker rm -f ofs` and run again with the same mounts and env file: steps 5-7 still pass. Reboot the instance once and repeat.
9. Make wrong verify attempts from one network and confirm another network is not rate limited (proves real client IPs through the proxy).
10. A 6 MB PDF is refused, a non-PDF is refused, a normal PDF uploads.
11. Run the backup script and a restore rehearsal (section 9).
12. Option S only: the object appears in the bucket, the bucket is not public, downloads redirect to a short-lived signed URL, and the instance role is the only credential in use.

## 11. Avoiding surprise AWS charges (verify current pricing yourself; none is assumed here)

- One instance, one EBS volume, one Elastic IP attached to the running instance. Unattached Elastic IPs, public IPv4 addresses, volumes left after stopping or terminating an instance, snapshots and S3 versions can all be billed.
- Create a billing budget/alert before launching. Tag everything for this project. Delete test instances, volumes, snapshots and buckets after trials.
- Do not create NAT gateways, load balancers, RDS or EFS; none are needed.
- Define a snapshot/backup retention period so old copies do not accumulate.
- Do not assume free-tier eligibility or promotional credits; confirm in the account's billing console.

## 12. Not proven yet (needs the real host)

- Ownership and permissions of the EBS mount for UID 10001; WAL behaviour on the real EBS filesystem (local tests used Docker Desktop bind mounts on Windows).
- The EBS, fstab, Caddy/Nginx, HSTS and cron commands above on the actual OS image.
- TLS, proxy IP handling and body-size limits end to end.
- S3 against real AWS and the IAM role scope (only `moto` tested).
- Real-browser admin flows.

## 13. Before DNS and launch

- **Sitemap/robots:** `frontend/public/sitemap.xml` and `robots.txt` ship in the image and use the canonical host `https://ourforeverstar.com` (apex, https). Serve and certify that exact host, and redirect `www.ourforeverstar.com` to it (Caddy: a second site block with `redir https://ourforeverstar.com{uri}`), otherwise the sitemap URLs will not match the site. `robots.txt` blocks only `/admin`, `/registry/` and `/api/`; production must not set `NOINDEX=true`, which would replace it with a Disallow-all file. Indexing is not guaranteed by these files; submit the sitemap in Search Console after launch.
- Hostinger DNS, only after section 10 passes on the temporary hostname: lower the TTL a day ahead; point the apex/`www` A record(s) at the Elastic IP (not the instance's changing public IP); remove conflicting A/AAAA/CNAME records for the same names; do not touch MX/TXT (email) records; add SPF/DKIM only if SMTP sending is used. Caddy or certbot issues the certificate once DNS resolves.
- Keep the old host available until verification passes on the real domain.
