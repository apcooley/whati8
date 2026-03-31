# PLAN.md — Migrate whati8 to GCP (Cloud Run + Cloud SQL)

## Goal
Move whati8 from Fly.io to GCP for reliable managed Postgres and low-latency hosting in Salt Lake City (`us-west3`).

## Architecture

```
User → Cloudflare DNS → Cloud Run (us-west3) → Cloud SQL PostgreSQL 16
          whati8.app       whati8:9428              managed, auto-backup
```

## Prerequisites
- GCP account (use aaronpcooley@gmail.com)
- `gcloud` CLI installed and authenticated
- Billing enabled (free trial gives $300 credit for 90 days)
- `whati8.app` domain (already owned on Cloudflare)

## Steps

### Step 1: GCP Project Setup
- Install `gcloud` CLI
- `gcloud auth login`
- Create project: `gcloud projects create whati8-prod --name="whati8"`
- Enable billing on the project
- Enable APIs: Cloud Run, Cloud SQL, Artifact Registry, Cloud Build
- Set default region: `gcloud config set run/region us-west3`

**Acceptance criteria:**
- `gcloud projects describe whati8-prod` works
- Required APIs enabled

### Step 2: Cloud SQL Instance
- Create Postgres 16 instance in `us-west3` (Salt Lake City):
  ```
  gcloud sql instances create whati8-db \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region=us-west3 \
    --storage-size=10 \
    --storage-auto-increase \
    --backup-start-time=04:00 \
    --availability-type=zonal
  ```
- Create database: `gcloud sql databases create whati8 --instance=whati8-db`
- Create user: `gcloud sql users create whati8 --instance=whati8-db --password=<generated>`
- Export local DB: `pg_dump -Fc` from NUC
- Import to Cloud SQL via `gcloud sql import` or Cloud SQL Auth Proxy + `pg_restore`
- Verify row counts match

**Acceptance criteria:**
- Cloud SQL instance running and healthy
- All 16 tables present, row counts match local
- Can connect via Cloud SQL Auth Proxy

### Step 3: Artifact Registry + Docker Image
- Create Artifact Registry repo:
  ```
  gcloud artifacts repositories create whati8 \
    --repository-format=docker \
    --location=us-west3
  ```
- Tag and push Docker image:
  ```
  docker build -t us-west3-docker.pkg.dev/whati8-prod/whati8/app:latest .
  docker push us-west3-docker.pkg.dev/whati8-prod/whati8/app:latest
  ```
- Or use Cloud Build: `gcloud builds submit --tag <image>`

**Acceptance criteria:**
- Image in Artifact Registry
- Image builds successfully from existing Dockerfile

### Step 4: Cloud Run Service
- Deploy:
  ```
  gcloud run deploy whati8 \
    --image=us-west3-docker.pkg.dev/whati8-prod/whati8/app:latest \
    --region=us-west3 \
    --port=9428 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=1 \
    --max-instances=3 \
    --allow-unauthenticated \
    --add-cloudsql-instances=whati8-prod:us-west3:whati8-db \
    --set-env-vars="ENVIRONMENT=prod,LOG_LEVEL=info" \
    --set-secrets="JWT_SECRET=jwt-secret:latest,ANTHROPIC_API_KEY=anthropic-key:latest,COHERE_API_KEY=cohere-key:latest"
  ```
- Cloud Run connects to Cloud SQL via Unix socket (no public IP needed)
- `DATABASE_URL` format: `postgresql://whati8:<pass>@/whati8?host=/cloudsql/whati8-prod:us-west3:whati8-db`
- `min-instances=1` keeps one instance warm (no cold starts)

**Acceptance criteria:**
- `curl https://whati8-<hash>-wl.a.run.app/health` returns healthy
- Login, search, food logging all work
- No DB connection errors

### Step 5: Custom Domain
- Map `whati8.app` to Cloud Run:
  ```
  gcloud run domain-mappings create --service=whati8 --domain=whati8.app --region=us-west3
  ```
- Update Cloudflare DNS:
  - Remove old A/AAAA records (Fly.io IPs)
  - Add new records per `gcloud run domain-mappings describe` output
  - Proxy OFF (Cloud Run handles TLS)
- Verify `https://whati8.app` works

**Acceptance criteria:**
- `https://whati8.app` serves the app with valid TLS
- Old Fly.io URLs stop working (expected)

### Step 6: Staging Environment on GCP
- Create staging Cloud Run service:
  ```
  gcloud run deploy whati8-staging \
    --image=<same image> \
    --region=us-west3 \
    --set-env-vars="ENVIRONMENT=staging,REGISTRATION_ENABLED=true"
  ```
- Staging uses same Cloud SQL instance, different database (`whati8_staging`)
- Or: use Neon free tier for staging DB (saves Cloud SQL costs)

**Acceptance criteria:**
- Staging accessible at its Cloud Run URL
- Isolated database from prod

### Step 7: Cleanup Fly.io
- Destroy Fly apps (after confirming GCP works for 24h):
  ```
  fly apps destroy whati8-app
  fly apps destroy whati8-staging
  fly apps destroy whati8-db
  fly apps destroy whati8-staging-db
  ```
- Remove `fly.toml` and `fly.staging.toml` from repo
- Update deploy scripts to use `gcloud`

**Acceptance criteria:**
- No Fly.io resources running
- No Fly.io charges
- GCP is the single deployment target

## Config Changes Needed
- `DATABASE_URL` format for Cloud SQL Unix socket (different from TCP)
- `whati8/database.py` — Cloud SQL uses Unix sockets, not TCP+SSL. The `connect_args` logic needs to detect `/cloudsql/` in the URL
- `ALLOWED_ORIGINS` — update to `["https://whati8.app"]` (same as now)
- `fly.toml` → `cloudbuild.yaml` or `gcloud run deploy` script

## Cost Estimate
| Service | Monthly |
|:--|:--|
| Cloud SQL db-f1-micro | ~$7 |
| Cloud Run (min 1 instance) | ~$5-10 |
| Artifact Registry | ~$0.10 |
| Network egress | ~$0.50 |
| **Total** | **~$13-18/mo** |

With $300 free trial credit, that's ~18 months free.

## Secrets (GCP Secret Manager)
```
gcloud secrets create jwt-secret --data-file=- <<< "<value>"
gcloud secrets create anthropic-key --data-file=- <<< "<value>"
gcloud secrets create cohere-key --data-file=- <<< "<value>"
gcloud secrets create db-password --data-file=- <<< "<value>"
```

## Rollback
If GCP doesn't work out:
- Fly.io apps can be recreated from the same Docker image
- DB can be restored from the local dump
- DNS switch back takes ~5 minutes
