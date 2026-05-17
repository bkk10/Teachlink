Production deployment checklist for Teachly

Fill these repository secrets (GitHub) and Vercel project settings before pushing to `main`:

- GITHUB secrets (for Actions):
  - `VERCEL_TOKEN` — Vercel personal token (with scope to deploy)
  - `VERCEL_ORG_ID` — Vercel organization ID
  - `VERCEL_PROJECT_ID` — Vercel project ID

- Vercel environment variables (Project Settings -> Environment Variables) or set via GitHub Actions secrets and Vercel integration:
  - `DJANGO_SECRET_KEY` — a strong secret key
  - `DEBUG` = `False`
  - `ALLOWED_HOSTS` — comma-separated domain(s) (e.g. `teachly.example.com`)
  - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — if using external Postgres
  - `REDIS_URL` — optional (Celery/cache)
  - `DEFAULT_FROM_EMAIL` — optional

How deployment works

- CI run (`.github/workflows/ci-cd.yml`) executes tests, builds the Docker image, pushes to GHCR, then triggers Vercel deployment using `amondnet/vercel-action`.
- `vercel.json` tells Vercel to build the provided `Dockerfile`.
- Container entrypoint (`entrypoint.sh`) runs migrations and `collectstatic` then starts Gunicorn.

Local testing

Build and run locally with Docker Compose (production config):

```bash
# copy .env.example -> .env and edit
docker compose -f docker-compose.prod.yml up --build
```

If you're using WSL/Unix, make `entrypoint.sh` executable locally:

```bash
chmod +x entrypoint.sh
```

Notes & next steps

- I left the original `teachlink/` package in place to avoid breaking anything during the rename. If you want, I can delete it after you verify everything is working.
- If you prefer the app to be served behind a managed platform load balancer (Render, DO App Platform), I can add provider-specific deploy steps.

If you want, I will now remove the old `teachlink/` package and run a final repo search to ensure no stray imports remain.
