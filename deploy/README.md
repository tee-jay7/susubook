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

Only the **password** is a secret. Host, port, database and role are ordinary
configuration and are passed as environment variables, so Secret Manager holds
exactly one value that needs protecting and the rest stays legible in the
service definition.

```bash
# The database password — created by hand, so the value never enters the
# repository, a config file, or a terminal transcript.
printf 'YOUR_PASSWORD' | gcloud secrets create susu-db-password --data-file=-
```

`./deploy/deploy.sh setup` generates the session signing key
(`susubook-secret-key`) if it does not already exist, and grants the Cloud Run
runtime service account `secretAccessor` on both.

The application composes the connection URL from these parts at startup
(`app/config.py::resolve_database_url`), percent-encoding the password so that
a `@`, `:`, `/`, `#` or `?` in it cannot corrupt the URL.

## Deploy

The project defaults to the gcloud CLI's configured project.

```bash
./deploy/deploy.sh setup      # once: APIs, registry, signing key, secret IAM
./deploy/deploy.sh deploy     # build image, deploy service
./deploy/deploy.sh db-init    # create schema  (TD-01: no migrations)
./deploy/deploy.sh seed       # load demo accounts and data
./deploy/deploy.sh url        # print the live URL
```

Subsequent releases are `./deploy/deploy.sh deploy`. Images are tagged with the
short git SHA, so a deployed revision is traceable to a commit.

## Verify

```bash
curl -s "$(./deploy/deploy.sh url)/health"
# {"database":"ok","status":"ok"}
```

`/health` reports database reachability and is unauthenticated — a probe cannot
log in. It returns a status only: no version, hostname or error detail.

> **Why `/health` and not `/healthz`.** The conventional Kubernetes-style path
> does not work on Cloud Run: **Google Front End intercepts `/healthz` and
> answers it with its own 404 before the request reaches the container.**
>
> This was established empirically, because the symptom is misleading — the
> route is registered, the container serves it correctly, and the application
> looks broken. Three observations identified it: the identical image returns
> `200` for `/healthz` when run locally; requests to `/healthz` never appear in
> Cloud Run's request log at all, while `/nope` does; and of eleven candidate
> paths tested through the deployed service, `/healthz` was the *only* one
> intercepted. `/health`, `/livez`, `/readyz`, `/status`, `/ping` and the rest
> all reach the application.

## Operational characteristics

| | |
|---|---|
| **Cold start** | Scale-to-zero means the first request after idle waits for a container start — measured in seconds, not the ~50 s of a suspended free-tier PaaS. `--min-instances=1` removes it entirely at roughly $5–15/month. |
| **Latency** | `us-central1` is roughly 150–200 ms from Ghana. Chosen for Compute Engine free-tier eligibility; a closer region would serve the intended users better but is not free. Recorded as a documented trade-off, not an oversight. |
| **TLS** | Terminated by Cloud Run with a Google-managed certificate. The application reads `X-Forwarded-Proto` when building absolute URLs for QR cards. |
| **Logs** | `./deploy/deploy.sh logs`, or Cloud Logging. Structured logging and alerting remain outstanding (TD-17). |
| **Schema changes** | Manual, because there are no migrations (TD-01). |
