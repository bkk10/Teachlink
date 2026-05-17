Production deployment checklist for Teachly

Deploying to Render (Docker-native platform):

Fill these repository secrets (GitHub) before pushing:

- GITHUB secrets (for Actions):
  - `RENDER_SERVICE_ID` — your Render service ID (visible in Render dashboard)
  - `RENDER_API_KEY` — your Render API key (from account settings)

How it works

- CI run (`.github/workflows/ci-cd.yml`) runs tests, then triggers Render deploy.
- `render.yaml` tells Render to build and serve the `Dockerfile`.
- Container entrypoint (`entrypoint.sh`) runs migrations and collectstatic, then starts Gunicorn on port 8000.

Setup steps

1. **Create a Render account** (free tier available): [render.com](https://render.com)
2. **Create a new Web Service**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click **"New +"** → **"Web Service"**
   - Connect your GitHub repo (`bkk10/Teachlink`)
   - Select `main` branch
   - Service name: `teachly`
   - Runtime: **Docker** ✓
   - Plan: **Free** (sleeps after 15 min inactive) or **Starter** ($7/mo for always-on)
   - Region: Oregon (or closest to you)
   - Click **Create Web Service**
3. **Set environment variables in Render** (Service → Environment):
   - `DJANGO_SECRET_KEY` — generate one:
     ```bash
     python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
     ```
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `teachly.onrender.com` (or your production domain)
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — if using external Postgres (optional)
4. **Get GitHub secrets**:
   - In Render → Account → [API Keys](https://dashboard.render.com/account/api-keys) → Create Key → copy it
   - In your Render service → Settings → scroll to find **Service ID** → copy it
5. **Add GitHub Secrets** (repo Settings → Secrets and variables → Actions):
   - `RENDER_SERVICE_ID` = your service ID
   - `RENDER_API_KEY` = your API key
6. **Push to main**:
   ```bash
   git push origin main
   ```

The workflow will run tests and trigger Render to deploy. Your app will be live at `https://teachly.onrender.com`.

Local testing

```bash
# copy .env.example -> .env and edit with your settings
docker compose -f docker-compose.prod.yml up --build
```

On Unix/WSL, make `entrypoint.sh` executable:

```bash
chmod +x entrypoint.sh
```

Notes

- Render's free tier includes auto-sleeping after 15 minutes of inactivity. Upgrade to Starter ($7/mo) for always-on production.
- For a production database, use Render Postgres or an external managed database.


- Render auto-deploys on push to your connected branch.

