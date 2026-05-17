Production deployment checklist for Teachly

Deploying to Render (Docker-native platform):

Fill these repository secrets (GitHub) before pushing:

- GITHUB secrets (for Actions):
  - `RENDER_SERVICE_ID` — your Render service ID (visible in Render dashboard)
  - `RENDER_API_KEY` — your Render API key (from account settings)

How it works

- CI run (`.github/workflows/ci-cd.yml`) runs tests, builds Docker image, pushes to GHCR, then triggers Render deploy.
- `render.yaml` tells Render to build and serve the `Dockerfile`.
- Container entrypoint (`entrypoint.sh`) runs migrations and collectstatic, then starts Gunicorn on port 8000.

Setup steps

1. **Create a Render account** (free): [render.com](https://render.com)
2. **Create a new Web Service**:
   - Connect your GitHub repo
   - Select branch `main`
   - Enter name: `teachly`
   - Runtime: Docker ✓
   - Plan: Free (or paid for production)
   - Region: Oregon or closest to you
3. **Set environment variables in Render**:
   - `DJANGO_SECRET_KEY` — create one locally:
     ```bash
     python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
     ```
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `your-service-name.onrender.com` (Render provides this)
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — if using external Postgres
4. **Get deploy secrets**:
   - In Render dashboard → Account settings → API keys → copy your API key
   - In your deployed service → Settings → copy Service ID
5. **Add GitHub Secrets** (Settings → Secrets):
   - `RENDER_SERVICE_ID`
   - `RENDER_API_KEY`
6. **Push to main**:
   ```bash
   git push origin main
   ```

The workflow will test, build, push image to GHCR, then trigger Render to deploy.

Local testing

```bash
# copy .env.example -> .env and edit
docker compose -f docker-compose.prod.yml up --build
```

On Unix/WSL, make entrypoint executable:

```bash
chmod +x entrypoint.sh
```

Notes

- Render's free tier includes auto-sleeping after 15 minutes of inactivity. Upgrade to Starter ($7/mo) for always-on.
- Render auto-deploys on push to your connected branch.

