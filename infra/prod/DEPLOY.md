# TubeForge AI — production deploy (Coolify VPS)

Target: **https://tubeforge.aixentium.com** — Next.js SPA + Django API (`/api/v1`)
on one domain, Traefik path routing.

## 0. DNS (Cloudflare)

Create an **A record** `tubeforge` → the same VPS origin IP as
`fences.aixentium.com` (check the existing fences record and copy its IP).
Leave it **proxied** (orange cloud), same as the other app records.

## 1. Pull the repo

Paste into VPS SSH:

```bash
cd /root
if [ -d tubeforge-deploy ]; then
  cd tubeforge-deploy && git pull
else
  git clone https://github.com/softwareproscompany-debug/TubeForgeAI.git tubeforge-deploy
  cd tubeforge-deploy
fi
```

## 2. Create the env file

```bash
cp infra/prod/.env.example infra/prod/.env
# Generate secrets and paste them into infra/prod/.env:
openssl rand -base64 48   # -> SECRET_KEY
openssl rand -base64 32   # -> POSTGRES_PASSWORD
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # -> FERNET_KEY
nano infra/prod/.env
```

Required values: `POSTGRES_PASSWORD`, `SECRET_KEY`, `FERNET_KEY`.
Everything else has working defaults for `tubeforge.aixentium.com`.

## 3. Build and start

```bash
cd /root/tubeforge-deploy
docker compose -f infra/prod/docker-compose.prod.yml --env-file infra/prod/.env up -d --build
docker compose -f infra/prod/docker-compose.prod.yml --env-file infra/prod/.env ps
```

The API container runs migrations + `collectstatic` on boot, so the first
start takes a minute. Watch it:

```bash
docker logs -f tubeforge-api
```

## 4. Create the admin user

```bash
docker exec -it tubeforge-api python manage.py createsuperuser
```

## 5. Register the Traefik route

```bash
cp /root/tubeforge-deploy/infra/prod/traefik/tubeforge.yaml /data/coolify/proxy/dynamic/tubeforge.yaml
```

The file provider has `watch=true` — no Traefik restart needed. Let's Encrypt
issues the cert on first HTTPS hit (can take ~1 minute).

## 6. Verify

- https://tubeforge.aixentium.com → app shell loads
- https://tubeforge.aixentium.com/api/v1/ → API responds (auth required is fine)
- `docker exec tubeforge-api python manage.py check` → no errors

## Phase 2 (not in this bundle)

- **Temporal server + workers** (`temporal_worker`, `render_worker`, `ai_gateway`):
  durable workflow execution instead of the current sync fallback.
- **MinIO / S3-compatible object storage** for binary assets.
- **GPU profile**: ComfyUI + local inference containers on a GPU host.
- Move `migrate` out of the API boot sequence into a one-shot init container
  once a second API replica is added.

## Rollback

```bash
cd /root/tubeforge-deploy
docker compose -f infra/prod/docker-compose.prod.yml --env-file infra/prod/.env down
# Traefik route removal:
rm /data/coolify/proxy/dynamic/tubeforge.yaml
```

Data survives in the `pgdata` / `redisdata` volumes unless removed explicitly
(`docker volume rm tubeforge-prod_pgdata` — destructive, don't).

## GitHub Actions auto-deploy (optional, recommended)

Every push to `main` can redeploy the VPS automatically.

**One-time VPS setup** — paste into SSH:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/tubeforge-deploy -N "" -C "tubeforge-github-actions"
cat /root/.ssh/tubeforge-deploy.pub >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
echo "--- paste the key below into the VPS_SSH_KEY repo secret ---"
cat /root/.ssh/tubeforge-deploy
```

**Repo secrets** (repo → Settings → Secrets and variables → Actions):
- `VPS_HOST` — VPS hostname or IP (e.g. `srv2057485.hstgr.cloud`)
- `VPS_SSH_KEY` — the private key printed above (starts with `-----BEGIN OPENSSH PRIVATE KEY-----`)

**Activate the workflow** (the app token cannot write to `.github/workflows/`,
so this is a manual copy, same as `ci.yml`):
1. On github.com → Add file → Create new file.
2. Name it exactly `.github/workflows/deploy.yml`, paste the contents of
   `infra/deploy.yml`, commit.

**Also fix:** if `.GitHub/workflows/ci.yml` (capital G) exists, GitHub Actions
ignores it — open it in the web UI, hit Edit, and rename the path to the
lowercase `.github/workflows/ci.yml`.
