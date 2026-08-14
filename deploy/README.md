# Deployment

SusuBook runs as a container on **Cloud Run**, against **PostgreSQL on a Compute
Engine VM** inside the default VPC. The database has no public address.

```
                    ┌──────────────────────────────────────────┐
   Internet ───────▶│  Cloud Run: susubook (us-central1)        │
   (HTTPS,          │  scale-to-zero · max 4 instances          │
    Google-managed  │  secrets from Secret Manager              │
    certificate)    └───────────────────┬──────────────────────┘
                                        │ Direct VPC egress
                                        │ (private ranges only)
                    ┌───────────────────▼──────────────────────┐
                    │  default VPC · 10.128.0.0/20             │
                    │   ┌────────────────────────────────────┐ │
                    │   │ susu-book-db  10.128.0.6            │ │
                    │   │ tag: susu-db · PostgreSQL :5432     │ │
                    │   │ firewall: 10.128.0.0/20 → tcp:5432  │ │
                    │   └────────────────────────────────────┘ │
                    └──────────────────────────────────────────┘
```

## Design notes

**Direct VPC egress, not a Serverless VPC Access connector.** A connector
provisions billable instances that run continuously, which would defeat a
free-tier deployment. Direct egress is configuration on the service itself.

**Region is fixed by the subnet.** `10.128.0.0/20` is the default-VPC range for
`us-central1`, and the firewall rule admits that range only. Cloud Run must
therefore deploy to `us-central1` so its instances draw addresses the rule
allows. Changing region means changing both.

**Admin tasks run as Cloud Run Jobs.** The database is private, so no developer
machine can reach it. Schema creation and seeding execute from inside the VPC
using the same image and the same secret — no SSH tunnel, and the password never
leaves Secret Manager.

**One image, two workloads.** The service and the jobs share an image, so an
admin task cannot drift from the application it maintains.

**Small connection pool.** Several Cloud Run instances, each with two gunicorn
workers, all share one small PostgreSQL server. Pools are capped at 2+3 per
worker and instances at 4, bounding the system at well under the server's limit.

## Prerequisites

- `gcloud` authenticated: `gcloud auth login`
- Billing enabled on the project
- PostgreSQL reachable on the VM's private address, with `listen_addresses`
  including it and `pg_hba.conf` admitting `10.128.0.0/20`
- The database and role created

## Secrets

Created once, by hand, so credentials never enter the repository or a transcript:

```bash
printf 'postgresql+psycopg://susu_app:PASSWORD@10.128.0.6:5432/susu_book' | \
  gcloud secrets create susubook-database-url --data-file=- --project=PROJECT_ID

python3 -c "import secrets; print(secrets.token_hex(32))" | \
  gcloud secrets create susubook-secret-key --data-file=- --project=PROJECT_ID
```

`+psycopg` selects psycopg 3. Plain `postgresql://` makes SQLAlchemy look for
psycopg2, which is not installed.

## Deploy

```bash
export PROJECT_ID=your-project-id

./deploy/deploy.sh setup      # once: enable APIs, create registry, grant secret access
./deploy/deploy.sh deploy     # build image, deploy service
./deploy/deploy.sh db-init    # create schema  (TD-01: no migrations)
./deploy/deploy.sh seed       # load demo accounts and data
./deploy/deploy.sh url        # print the live URL
```

Subsequent releases are `./deploy/deploy.sh deploy`. Images are tagged with the
short git SHA, so a deployed revision is traceable to a commit.

## Verify

```bash
curl -s "$(./deploy/deploy.sh url)/healthz"
# {"database":"ok","status":"ok"}
```

`/healthz` reports database reachability and is unauthenticated — a probe cannot
log in. It returns a status only: no version, hostname or error detail.

## Operational characteristics

| | |
|---|---|
| **Cold start** | Scale-to-zero means the first request after idle waits for a container start — measured in seconds, not the ~50 s of a suspended free-tier PaaS. `--min-instances=1` removes it entirely at roughly $5–15/month. |
| **Latency** | `us-central1` is roughly 150–200 ms from Ghana. Chosen for Compute Engine free-tier eligibility; a closer region would serve the intended users better but is not free. Recorded as a documented trade-off, not an oversight. |
| **TLS** | Terminated by Cloud Run with a Google-managed certificate. The application reads `X-Forwarded-Proto` when building absolute URLs for QR cards. |
| **Logs** | `./deploy/deploy.sh logs`, or Cloud Logging. Structured logging and alerting remain outstanding (TD-17). |
| **Schema changes** | Manual, because there are no migrations (TD-01). |
