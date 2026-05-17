Production deployment checklist for Teachly

Deploying to Vercel (Python serverless):

Fill these repository secrets (GitHub) before pushing:

- GITHUB secrets (for Actions):
  - `VERCEL_TOKEN` — Vercel personal token from [vercel.com/account/tokens](https://vercel.com/account/tokens)
  - `VERCEL_ORG_ID` — Your Vercel org ID (visible in dashboard/URL)
  - `VERCEL_PROJECT_ID` — Your Vercel project ID (from project settings)

How it works

- CI run (`.github/workflows/ci-cd.yml`) runs tests, then deploys directly to Vercel using `amondnet/vercel-action`.
- `vercel.json` configures Vercel to run `pip install`, collectstatic, and serve via `api/index.py`.
- `api/index.py` is a serverless function that wraps the Django WSGI app.

Setup steps

1. **Create a Vercel account** (free tier available): [vercel.com](https://vercel.com)
2. **Create a new project**:
   - Go to [Vercel Dashboard](https://dashboard.vercel.com)
   - Click "Add New" → "Project"
   - Import your GitHub repo (`bkk10/Teachlink`)
   - Vercel will auto-detect the project and suggest settings
3. **Set environment variables in Vercel** (Project Settings → Environment Variables):
   - `DJANGO_SECRET_KEY` — generate one:
     ```bash
     python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
     ```
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `your-project-name.vercel.app` (your actual Vercel domain)
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — if using external Postgres (optional)
4. **Get GitHub secrets**:
   - In Vercel → Account → [Settings → Tokens](https://vercel.com/account/tokens) → Create Token → copy it
   - In Vercel Dashboard, select your project → Settings → copy **Project ID**
   - Find your **Org ID** in the URL or account settings
5. **Add GitHub Secrets** (repo Settings → Secrets and variables → Actions):
   - `VERCEL_TOKEN` = your Vercel token
   - `VERCEL_ORG_ID` = your org ID
   - `VERCEL_PROJECT_ID` = your project ID
6. **Push to main**:
   ```bash
   git push origin main
   ```

The workflow will run tests and deploy to Vercel. Your app will be live at `https://your-project-name.vercel.app`.

Notes

- Vercel's free tier works for development/testing. Upgrade to Pro ($20/mo) for production with better performance.
- For a real database, add Vercel Postgres or use an external Postgres service.
- If you hit serverless cold-start delays, consider upgrading to a managed instance or Platform.

- Render auto-deploys on push to your connected branch.

