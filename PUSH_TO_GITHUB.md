# Push GeoSamanvay to GitHub

Run these commands in order from `D:\SIH_FINAL_v5\sih26013_latest`.

## Step 1 — Authenticate GitHub CLI
```powershell
gh auth login
# Choose: GitHub.com → HTTPS → Login with browser
```

## Step 2 — Create repo and push (one command)
```powershell
cd D:\SIH_FINAL_v5\sih26013_latest
gh repo create sih26013 --public --source=. --remote=origin --push --description "GeoSamanvay: Evidence-Aware Multi-Source Geospatial Harmonization — SIH26013 Team Aikta"
```

This creates `github.com/<your-username>/sih26013`, sets `origin`, and pushes the existing commit.

## Step 3 — Add repo topics
```powershell
gh repo edit sih26013 --add-topic "sih2026,geospatial,harmonization,land-records,fastapi,react,india,government,naksha,ulpin"
```

## Step 4 — Verify
```powershell
gh repo view sih26013 --web
```

---

## Deploy to Render (after GitHub push)

1. Go to https://render.com → New → Web Service → Connect GitHub → select `sih26013`
2. Render detects `render.yaml` automatically — click **Apply**
3. Wait ~5 min for the Docker build
4. Health check: `https://<your-service>.onrender.com/api/v1/health`
5. Load demo: `POST https://<your-service>.onrender.com/api/v1/demo/load-ward42`

Or via CLI after logging in:
```powershell
# Install render CLI: https://render.com/docs/cli
render deploy --service geosamanvay
```

The `render.yaml` is already committed:
- Runtime: Docker
- Plan: Free
- Health check: `/api/v1/health`
- Auto-deploy: on push to main
