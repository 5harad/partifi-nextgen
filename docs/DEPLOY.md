# Production cutover — partifi.org

This runbook deploys **partifi-nextgen** on a single EC2 instance with Docker Compose, imports legacy score/partset metadata into a fresh MySQL database, and points **partifi.org** at the new stack. Files stay in the existing **`cdn.partifi.org`** S3 bucket.

## What gets migrated

| Imported | Skipped |
|----------|---------|
| `scores`, `partsets`, `pages`, `segments`, `breaks`, `parts` | `users`, `favorites` |
| `original_pages`, `original_segments` | `donations`, `downloads` |
| `imslp_info`, `composers` | |

Legacy **public download links** (`https://partifi.org/{publicId}`) and **editor links** (`https://partifi.org/{privateId}/…`) keep working because ids are preserved. Users sign in fresh with Google; old Facebook library links do not carry over.

---

## 1. Pre-flight (do before cutover day)

### AWS & DNS

- [ ] EC2 instance in the **same region** as the S3 bucket (`cdn.partifi.org`)
- [ ] Instance type: **t4g.xlarge** (4 vCPU, 16 GB) recommended for the full corpus; **t4g.medium** only for smoke tests
- [ ] Elastic IP allocated and associated
- [ ] Security group: **22** (your IP), **80**, **443**
- [ ] IAM user or instance role: `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`, `s3:DeleteObject` on `cdn.partifi.org`
- [ ] Lower TTL on `partifi.org` A record to **300** one day ahead

### Secrets (rotate — legacy repo had leaks)

- [ ] New `APP_SECRET` (64+ random bytes)
- [ ] New MySQL passwords (`MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`)
- [ ] New AWS access keys for the app (revoke old keys after cutover)

### Google OAuth

In [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → your Web client:

- [ ] **Authorized JavaScript origins:** `https://partifi.org`
- [ ] **Authorized redirect URIs:** (if used) `https://partifi.org`
- [ ] Copy client id into `GOOGLE_CLIENT_ID` and `VITE_GOOGLE_CLIENT_ID`

---

## 2. Prepare the EC2 host

```bash
# Ubuntu 24.04
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"
# log out and back in
```

### Host memory (recommended on 16 GB instances)

Add **2–4 GB swap** so rare spikes (three heavy jobs + MySQL) swap instead of OOM-killing the kernel:

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Clone the repo:

```bash
git clone https://github.com/5harad/partifi-nextgen.git
cd partifi-nextgen
```

Create production env:

```bash
cp .env.production.example .env
# Edit .env — fill every blank value; set APP_ENV=production
```

---

## 3. Build and start (before DNS)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This starts:

| Service | Role |
|---------|------|
| `web` | Caddy — TLS, static React app, `/api` proxy |
| `api` | FastAPI (2 workers) |
| `mysql` | Fresh schema from `docker/mysql/init.sql` |
| `redis` | Job queue |
| `worker-1` … `worker-3` | Background jobs (4 GB memory cap each) |

Production compose sets **MySQL `innodb_buffer_pool_size = 4G`** (`docker/mysql/prod.cnf`) and **4 GB Docker memory limits** on each worker so a runaway PDF job is killed in its container instead of taking down the host.

Verify health (on the EC2 host; Caddy redirects HTTP→HTTPS, so use HTTPS locally or hit the API directly):

```bash
docker compose -f docker-compose.prod.yml exec -T api python -c "
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/health/ready') as r:
    print(json.dumps(json.load(r), indent=2))
"

# --resolve sets TLS SNI to your site name (cert is not valid for bare 127.0.0.1)
curl -sk --resolve "${SITE_ADDRESS:-partifi.org}:443:127.0.0.1" \
  "https://${SITE_ADDRESS:-partifi.org}/health/ready"
```

---

## 4. Import legacy partsets

The legacy MySQL server must be reachable from EC2 (VPN, SSH tunnel, or temporary security-group rule).

**During bulk import or long `CREATE INDEX` runs:** stop workers (and optionally the API) so they do not compete with MySQL for RAM and disk I/O:

```bash
docker compose -f docker-compose.prod.yml stop worker-1 worker-2 worker-3
# optional: docker compose -f docker-compose.prod.yml stop api
```

Start them again after import and index builds:

```bash
docker compose -f docker-compose.prod.yml start api worker-1 worker-2 worker-3
```

**Before import:** target id columns must use `utf8mb4_bin` (case-sensitive) so legacy ids like `03mra` and `03mrA` remain distinct. On an existing database:

```bash
docker compose -f docker-compose.prod.yml exec -T mysql \
  mysql -u root -p"$MYSQL_ROOT_PASSWORD" partifi < scripts/alter_case_sensitive_ids.sql
```

Fresh installs from current `docker/mysql/init.sql` already use the correct collations.

### Option A — SSH tunnel to legacy DB

On your laptop:

```bash
ssh -L 3307:127.0.0.1:3306 user@legacy-linode-host
```

On EC2:

```bash
export LEGACY_MYSQL_HOST=host.docker.internal   # or tunnel endpoint IP
export LEGACY_MYSQL_PORT=3307
export LEGACY_MYSQL_USER=partifi
export LEGACY_MYSQL_PASSWORD='legacy-password'

export TARGET_MYSQL_HOST=127.0.0.1
export TARGET_MYSQL_PORT=3306
export TARGET_MYSQL_USER=partifi
export TARGET_MYSQL_PASSWORD='from-.env'

# Inspect counts
./scripts/import-legacy-partsets.sh --dry-run

# Import (truncates content tables on target first)
./scripts/import-legacy-partsets.sh --confirm
```

If MySQL runs inside Docker on EC2, use the container IP or expose port 3306 on localhost only:

```bash
docker compose -f docker-compose.prod.yml exec mysql mysql -u partifi -p partifi -e "SELECT COUNT(*) FROM partsets"
```

### Option B — mysqldump file

On legacy:

```bash
mysqldump partifi scores partsets original_pages original_segments pages segments parts imslp_info composers \
  --no-create-info --default-character-set=utf8mb4 > legacy_content.sql
# Export breaks separately if needed; or use the Python script above (recommended)
```

Load into prod MySQL after adapting column lists, or prefer **Option A** (the script handles schema differences).

---

## 5. Smoke test on Elastic IP

Before switching DNS, test via the Elastic IP using a Host header (Caddy routes by hostname):

```bash
curl -s -H 'Host: partifi.org' http://ELASTIC_IP/health/ready
curl -s -H 'Host: partifi.org' http://ELASTIC_IP/api/v1/csrf-token
```

HTTPS / Let's Encrypt requires the public DNS A record to point at this server first (step 6).

Before DNS (HTTP + Host header):

- [ ] `/health/ready` returns ok
- [ ] Search returns imported scores (via browser with Host header or after DNS)

After DNS + TLS:

- [ ] https://partifi.org/ loads
- [ ] Search returns imported scores
- [ ] Open a legacy public link `/{publicId}` — parts download
- [ ] Open a legacy editor link `/{privateId}/segment` — segment editor loads
- [ ] New PDF upload → import → segment → preview → partgen → download
- [ ] Google sign-in → library add/remove

---

## 6. DNS cutover

1. Stop writes on legacy (maintenance page or stop Apache on Linode)
2. Run a **final** `./scripts/import-legacy-partsets.sh --confirm` if anything changed since step 4
3. Point **partifi.org** A record → Elastic IP
4. Optional aliases (Caddy redirects these to `https://partifi.org`):
   - **partifi.com** → Elastic IP (A)
   - **www.partifi.com** → Elastic IP (A or CNAME to `partifi.org`)
   - **www.partifi.org** → Elastic IP (A or CNAME to `partifi.org`)
5. Caddy obtains Let's Encrypt certificates automatically (ports 80/443 must be open)
6. Monitor:

```bash
docker compose -f docker-compose.prod.yml logs -f web api worker-1
```

---

## 7. Post-cutover

- [ ] Revoke legacy AWS keys
- [ ] Keep Linode read-only for 2 weeks as rollback reference
- [ ] Confirm `cdn.partifi.org` bucket is unchanged (same keys)
- [ ] Optional: remove temporary legacy DB tunnel / security-group rules

---

## Operations

### Memory and workers

| Setting | Value | Where |
|---------|-------|--------|
| Worker container cap | **4 GB** each | `docker-compose.prod.yml` |
| MySQL buffer pool | **4 GB** | `docker/mysql/prod.cnf` |
| Worker count | **3** | compose services |
| Job timeout | **45 min** | `JOB_TIMEOUT_SECONDS` in `.env` |
| Page workers per job | **auto** (half of CPU) | `PARTGEN_POOL_SIZE=0` in `.env` |

On a **16 GB** host the budget is roughly: ~1 GB OS, ~4 GB MySQL buffer pool, ~0.5–1 GB API/Caddy/Redis, up to **12 GB** if all three workers peak at once (rare). Swap covers that edge case.

If you routinely run **three large PDF imports at the same time**, set `PARTGEN_POOL_SIZE=1` in `.env` and recreate workers, or reduce to two worker containers.

After changing `prod.cnf` or memory limits, recreate affected containers:

```bash
docker compose -f docker-compose.prod.yml up -d mysql worker-1 worker-2 worker-3
```

Confirm MySQL picked up the buffer pool size:

```bash
docker compose -f docker-compose.prod.yml exec mysql \
  mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SHOW VARIABLES LIKE 'innodb_buffer_pool_size';"
```

### Reboot behavior

All prod services use **`restart: unless-stopped`** in `docker-compose.prod.yml` (`web`, `api`, `mysql`, `redis`, `worker-1` … `worker-3`). After an EC2 reboot:

1. The **Docker daemon** must start (Ubuntu: `systemctl is-enabled docker` → `enabled`).
2. Docker restarts any container that was **running** before shutdown.
3. Named volumes (`mysql_data`, `caddy_data`, etc.) persist — data is not lost.

**Containers you manually stopped** (e.g. `docker compose … stop worker-1 worker-2 worker-3` during import) **stay stopped** after reboot until you start them again:

```bash
docker compose -f docker-compose.prod.yml start api worker-1 worker-2 worker-3
```

On boot, containers start in parallel (compose `depends_on` does not serialize a host reboot). MySQL may take 10–30 seconds to accept connections; the API and workers usually recover on their own once Redis and MySQL are up.

**Does not survive reboot:** SSH tunnels to the legacy Linode DB, one-off shell sessions, anything outside Docker unless configured separately (cron, etc.).

One-time check that Docker starts on boot:

```bash
sudo systemctl enable docker
```

After reboot, verify:

```bash
docker compose -f docker-compose.prod.yml ps
curl -sk --resolve "${SITE_ADDRESS:-partifi.org}:443:127.0.0.1" \
  "https://${SITE_ADDRESS:-partifi.org}/health/ready"
```

### Restart after deploy

```bash
cd ~/partifi-nextgen

# Optional: save logs before containers are recreated
sudo mkdir -p /var/log/partifi
docker compose -f docker-compose.prod.yml logs --since 24h api worker-1 worker-2 worker-3 web \
  > "/var/log/partifi/pre-deploy-$(date +%F-%H%M).log" 2>&1 || true

git pull

# After this deploy (journald logging): recreate app containers once so the new log driver applies
docker compose -f docker-compose.prod.yml up -d --build --force-recreate web api worker-1 worker-2 worker-3

docker compose -f docker-compose.prod.yml ps
curl -sk --resolve "${SITE_ADDRESS:-partifi.org}:443:127.0.0.1" \
  "https://${SITE_ADDRESS:-partifi.org}/health/ready"
```

**One-time on existing databases** (adds `import_size` to `partsets.error` for oversize import failures):

```bash
docker compose -f docker-compose.prod.yml exec -T mysql \
  mysql -u root -p"$MYSQL_ROOT_PASSWORD" partifi < scripts/alter_add_import_size_error.sql
```

**Failure metadata** (`error_message`, `error_ts`, `last_job_id` on `partsets`):

```bash
docker compose -f docker-compose.prod.yml exec -T mysql \
  mysql -u root -p"$MYSQL_ROOT_PASSWORD" partifi < scripts/alter_add_failure_metadata.sql
```

Fresh installs from current `docker/mysql/init.sql` already include both migrations.

### Monitoring

#### External health check (recommended)

Use a third-party uptime monitor (UptimeRobot, Better Stack, etc.) — **not** a cron on the same EC2 box.

| Setting | Value |
|---------|--------|
| URL | `https://partifi.org/health/ready` |
| Interval | 5 minutes |
| Success | HTTP 200 and JSON `"status":"ok"` (MySQL, Redis, S3 all ok) |
| Alert | Email or Slack when down for 2+ checks |

`/health` only returns liveness; use **`/health/ready`** for dependency checks.

#### Diagnostic script (when something feels wrong)

SSH to the host and run:

```bash
cd ~/partifi-nextgen
chmod +x scripts/diagnostics.sh   # once
./scripts/diagnostics.sh
```

Optional: `DAYS=30 ./scripts/diagnostics.sh` for a longer activity/error window (default 7 days).

The script prints:

1. **Readiness** — local `/health/ready`
2. **Cache size** — total and by `scores/` / `preview/` / `parts/`
3. **Activity** — partsets with parts, part PDFs produced, imports completed, downloads (last 7 days by default)
4. **Failed partsets** — MySQL rows with `error` set or imports stuck &gt; 1 hour
5. **Recent errors** — journald (or docker logs fallback) from api + workers + web
6. **Container status** — `docker compose ps`

**What each layer tells you:**

| Layer | Good for | Not good for |
|-------|----------|--------------|
| External health check | Site down, API/DB/Redis/S3 broken | Stuck imports, cache full |
| DB (`partsets.error`) | Which jobs failed, at what stage | Root cause, warm-page failures |
| Logs (journald) | Exceptions, timeouts, OOM | Pre-import home-page rejections |
| Cache `du` | Growth, segment warm issues | User-facing error text |

#### Logs (journald)

Production compose sends **api**, **workers**, and **web** logs to **journald** (survives container recreate). **mysql** and **redis** use rotated `json-file` logs.

Recent errors (last 6 hours) — prefer `./scripts/diagnostics.sh`, which skips benign Caddy client disconnects and Ghostscript PDF warnings:

```bash
journalctl --since "6 hours ago" --no-pager \
  | grep -E 'partifi-nextgen-(api|worker|web)' \
  | grep -iE ' ERROR |exception|failed|timed out|exit 137|OOM|Traceback|ValueError|Could not' \
  | grep -viE 'aborting with incomplete response|http2: stream closed|repaired or ignored|The following errors were encountered'
```

Per-container (tag set in compose):

```bash
journalctl -t partifi/partifi-nextgen-api-1 --since "6 hours ago"
journalctl -t partifi/partifi-nextgen-worker-1-1 --since "6 hours ago"
```

`docker compose logs` still works for live tailing:

```bash
docker compose -f docker-compose.prod.yml logs -f api worker-1 worker-2 worker-3
```

Limit journal disk use on the host (optional, in `/etc/systemd/journald.conf`):

```ini
SystemMaxUse=500M
```

Then: `sudo systemctl restart systemd-journald`.

Pre-deploy log snapshots (before `git pull`) are written to `/var/log/partifi/pre-deploy-*.log` — see **Restart after deploy** above.

Daily cache cleanup output: `/var/log/partifi-clean-cache.log` (cron in **S3 vs local cache** below).

### Backups

```bash
docker compose -f docker-compose.prod.yml exec mysql \
  mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" partifi \
  | gzip > partifi-$(date +%F).sql.gz
```

MySQL data lives in the `mysql_data` volume. Back up regularly; S3 files are already durable separately.

### S3 vs local cache

**S3 (`cdn.partifi.org`)** stores **score PDFs only**: `scores/{score_id}_score.pdf`. That matches legacy `s3_push` — durable archive for the ~1.4 TB corpus.

**EC2 local cache** (`PARTIFI_CACHE_ROOT`, default `/data/partifi`) holds everything else: page PNGs, preview segment cuts, and generated part PDFs. The API and all workers share the **`partifi_cache`** Docker volume.

Layout:

```text
S3:
  scores/{score_id}_score.pdf

/data/partifi/
  scores/{score_id}/lowres|highres|thumbs/
  preview/{partset_id}/s0.png …
  parts/{partset_id}/*.pdf
```

Import and partgen write PNGs/parts to local cache only (not S3). Legacy scores without cached PNGs are warmed from the S3 PDF on first segment/preview visit. Local files are evicted when cold or over the size cap. The API serves cache via `/page-image/`, `/preview-segment/`, and `/part-file/` routes (see README). Saving segments or layout invalidates that partset's preview and part PDF cache entries.

**Check usage on the host:**

```bash
docker compose -f docker-compose.prod.yml exec api du -sh /data/partifi
```

**Optional bind mount** (instead of the named volume): create `/opt/partifi/cache` on the host and replace the `partifi_cache:` volume entries in `docker-compose.prod.yml` with:

```yaml
- /opt/partifi/cache:/data/partifi
```

**Daily cleanup** (TTL eviction + stale job scratch under `/tmp/partifi`):

```bash
# crontab -e on the EC2 host (04:00 UTC daily)
sudo mkdir -p /var/log/partifi
0 4 * * * cd /home/ubuntu/partifi-nextgen && docker compose -f docker-compose.prod.yml exec -T worker-1 python -m jobs.clean_cache >> /var/log/partifi-clean-cache.log 2>&1
```

Tune retention in `.env`: `PARTIFI_CACHE_MAX_GB`, `PARTIFI_CACHE_*_TTL_DAYS`, `PARTIFI_CACHE_SCRATCH_MAX_AGE_HOURS`.

Evicting cold **parts** cache sets `parts_ready = 0` for that partset (legacy behavior); the next download regenerates from layout.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Something feels wrong | `./scripts/diagnostics.sh` (cache + DB + logs) |
| Worker OOM / exit 137 | `journalctl` or `docker compose … logs worker-1`; score may be very large — retry; lower concurrency or raise cap in compose |
| Host sluggish / OOM | `free -h`; swap enabled? three heavy jobs at once? stop workers during maintenance |
| Jobs never run | `docker compose -f docker-compose.prod.yml ps` — all three workers up? Redis healthy? |
| Import stuck | Worker logs; `partsets.error` column; `JOB_TIMEOUT_SECONDS` |
| S3 403 | IAM policy, `S3_BUCKET`, region |
| Google login fails | Client id in `.env` **and** baked into frontend at build time (`VITE_GOOGLE_CLIENT_ID`); rebuild `web` after changing |
| TLS fails | DNS propagated? Ports 80/443 open? `docker compose … logs web` |
