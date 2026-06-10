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
- [ ] Instance type: **t4g.medium** (2 vCPU, 4 GB) or larger
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
| `worker-1` … `worker-3` | Background jobs |

Verify health (on the EC2 host):

```bash
curl -s http://localhost/health/ready
```

---

## 4. Import legacy partsets

The legacy MySQL server must be reachable from EC2 (VPN, SSH tunnel, or temporary security-group rule).

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
4. Caddy obtains a Let's Encrypt certificate automatically (ports 80/443 must be open)
5. Monitor:

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

### Restart after deploy

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Logs

```bash
docker compose -f docker-compose.prod.yml logs -f api worker-1 worker-2 worker-3
```

### Backups

```bash
docker compose -f docker-compose.prod.yml exec mysql \
  mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" partifi \
  | gzip > partifi-$(date +%F).sql.gz
```

MySQL data lives in the `mysql_data` volume. Back up regularly; S3 files are already durable separately.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Jobs never run | `docker compose -f docker-compose.prod.yml ps` — all three workers up? Redis healthy? |
| Import stuck | Worker logs; `partsets.error` column; `JOB_TIMEOUT_SECONDS` |
| S3 403 | IAM policy, `S3_BUCKET`, region |
| Google login fails | Client id in `.env` **and** baked into frontend at build time (`VITE_GOOGLE_CLIENT_ID`); rebuild `web` after changing |
| TLS fails | DNS propagated? Ports 80/443 open? `docker compose … logs web` |
