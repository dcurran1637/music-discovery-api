#  Quick Reference: Steps Outside Codespace

## Overview
This checklist covers all tasks you need to perform outside the GitHub Codespace to complete the deployment.

---

##  Pre-Deployment Checklist

### 1️⃣ Spotify Developer Setup (5 minutes)
**Location**: https://developer.spotify.com/dashboard

- [ ] Log in with Spotify account
- [ ] Click "Create app"
- [ ] Fill in details:
  - App name: **Music Discovery API**
  - Description: **Music discovery and playlist management**
  - Redirect URI: **https://music-discovery-api.onrender.com/api/auth/callback**
  - API: **Web API**
- [ ] Save app
- [ ] Copy **Client ID** → Save securely
- [ ] Click "View client secret" → Copy **Client Secret** → Save securely

** Keep these credentials safe! Never commit them to git.**

---

### 2️⃣ Render Account Setup (10 minutes)
**Location**: https://dashboard.render.com

- [ ] Sign up or log in to Render
- [ ] Click **"New +"** → **"Blueprint"**
- [ ] Click **"Connect GitHub"** (authorize if first time)
- [ ] Select repository: **music-discovery-api**
- [ ] Click **"Connect"**
- [ ] Review services to be created:
  -  Web Service: `music-discovery-api`
  -  PostgreSQL Database: `music-discovery-db`
  -  Redis Cache: `music-discovery-redis`
- [ ] Click **"Apply"**
- [ ] Wait 5-10 minutes for provisioning

---

### 3️⃣ Configure Render Environment (3 minutes)
**Location**: Render Dashboard → Your Service → Environment

- [ ] Go to `music-discovery-api` service
- [ ] Click **"Environment"** tab
- [ ] Add these variables:

```
SPOTIFY_CLIENT_ID = <paste-client-id-from-step-1>
SPOTIFY_CLIENT_SECRET = <paste-client-secret-from-step-1>
```

- [ ] Copy your Render service URL (e.g., `https://music-discovery-api-xyz.onrender.com`)
- [ ] Update `SPOTIFY_REDIRECT_URI`:
```
SPOTIFY_REDIRECT_URI = https://<your-render-url>/api/auth/callback
```

- [ ] Click **"Save Changes"**

---

### 4️⃣ Update Spotify Redirect URI (2 minutes)
**Location**: Spotify Developer Dashboard → Your App → Settings

- [ ] Return to https://developer.spotify.com/dashboard
- [ ] Open your app
- [ ] Click **"Settings"**
- [ ] Under **"Redirect URIs"**, click **"Edit"**
- [ ] Update with your actual Render URL:
```
https://<your-actual-render-url>/api/auth/callback
```
- [ ] Click **"Save"**

---

### 5️⃣ GitHub Secrets Setup (5 minutes)
**Location**: GitHub → Repository → Settings → Secrets

**Get Render API Key**:
- [ ] Go to Render Dashboard
- [ ] Click your avatar → **"Account Settings"**
- [ ] Click **"API Keys"** tab
- [ ] Click **"Create API Key"**
- [ ] Give it a name: **GitHub Actions**
- [ ] Copy the key → Save securely

**Get Render Service ID**:
- [ ] Go to your web service in Render
- [ ] Look at browser URL: `https://dashboard.render.com/web/srv-XXXXX`
- [ ] Copy the `srv-XXXXX` part

**Add to GitHub**:
- [ ] Go to your GitHub repository
- [ ] Click **"Settings"** → **"Secrets and variables"** → **"Actions"**
- [ ] Click **"New repository secret"**

Add Secret #1:
- [ ] Name: `RENDER_API_KEY`
- [ ] Value: `<paste-render-api-key>`
- [ ] Click **"Add secret"**

Add Secret #2:
- [ ] Name: `RENDER_SERVICE_ID`
- [ ] Value: `srv-XXXXX`
- [ ] Click **"Add secret"**

---

##  Deployment Execution

### Option A: Automatic (Git Push) - Recommended
**From your local machine or codespace**:

```bash
git add .
git commit -m "Deploy to Render with CI/CD"
git push origin main
```

Then:
- [ ] Go to GitHub repository → **"Actions"** tab
- [ ] Watch pipeline progress (6 jobs)
- [ ] Wait for all jobs to complete ( green)

---

### Option B: Manual Deploy (Render Dashboard)

- [ ] Go to Render Dashboard
- [ ] Select your service
- [ ] Click **"Manual Deploy"**
- [ ] Select **"Deploy latest commit"**
- [ ] Wait for deployment to complete

---

### Option C: Workflow Dispatch (GitHub)

- [ ] Go to GitHub repository → **"Actions"** tab
- [ ] Select **"CI/CD Pipeline"** workflow
- [ ] Click **"Run workflow"**
- [ ] Select branch: **main**
- [ ] Click **"Run workflow"**

---

##  Verification Steps

### Browser Verification
Open these URLs in your browser:

- [ ] Root: `https://<your-url>.onrender.com/`
  - Expected: JSON with API info
- [ ] Health: `https://<your-url>.onrender.com/api/health/live`
  - Expected: `{"status": "healthy"}`
- [ ] Docs: `https://<your-url>.onrender.com/docs`
  - Expected: Interactive API documentation
- [ ] OAuth: `https://<your-url>.onrender.com/api/auth/login`
  - Expected: Redirect to Spotify login

### Script Verification
Run from your local machine:

```bash
# Bash version
./scripts/verify_deployment.sh https://<your-url>.onrender.com

# Python version
python scripts/verify_deployment.py https://<your-url>.onrender.com
```

Expected: All tests pass 

---

##  Monitoring

### Check Deployment Status
- [ ] **Render Dashboard** → Service → Check status is **"Live"** (green)
- [ ] **Render Logs** → Service → Logs → Check no errors
- [ ] **GitHub Actions** → Latest workflow → All jobs passed

### Check Metrics
- [ ] **Render** → Service → Metrics → CPU/Memory usage normal
- [ ] **Render** → Service → Events → No restart events

---

##  Quick Troubleshooting

### If deployment fails:

**Check Render Logs**:
- [ ] Render Dashboard → Service → **Logs** tab
- [ ] Look for error messages in build or runtime logs

**Check Environment Variables**:
- [ ] Service → **Environment** tab
- [ ] Verify all required variables are set
- [ ] Check for typos in variable names

**Check GitHub Actions**:
- [ ] Repository → **Actions** tab
- [ ] Click failed workflow
- [ ] Expand failed job to see error

**Common Issues**:
-  Redirect URI mismatch → Check exact match in both Spotify and Render
-  Database error → Check DATABASE_URL is set
-  500 error → Check Render logs for exceptions
-  Tests fail → Run `pytest` locally first

---

##  Success Criteria

Your deployment is successful when:

- [x] Render service status shows **"Live"** (green)
- [x] GitHub Actions pipeline shows **all jobs passed** (6/6)
- [x] Root endpoint returns API information
- [x] Health check returns 200 OK
- [x] API docs are accessible at `/docs`
- [x] OAuth login redirects to Spotify
- [x] Protected endpoints return 401 without authentication
- [x] Verification script reports **"All tests passed"**
- [x] No errors in Render logs

---

##  Where to Get Help

### Documentation
- [Full Deployment Guide](./DEPLOYMENT.md)
- [Deployment Summary](./DEPLOYMENT_SUMMARY.md)
- [README](./README.md)

### External Resources
- **Render**: https://render.com/docs
- **GitHub Actions**: https://docs.github.com/actions
- **Spotify API**: https://developer.spotify.com/documentation

### Support Channels
- Render Dashboard: Chat support
- GitHub Issues: Report bugs
- Render Status: https://status.render.com

---

##  Congratulations!

Once all checkboxes are complete, you have:
-  Deployed a production-ready API to the cloud
-  Implemented automated CI/CD pipeline
-  Configured secure secrets management
-  Set up comprehensive monitoring
-  Verified authentication protection
-  Established enterprise-grade DevOps practices

**Your API is now live and automatically deployable!** 

---

##  Post-Deployment Tasks

### Optional Enhancements:
- [ ] Add custom domain in Render
- [ ] Set up uptime monitoring (UptimeRobot, Pingdom)
- [ ] Configure alerts for errors
- [ ] Add staging environment
- [ ] Implement blue-green deployments
- [ ] Set up log aggregation (LogDNA, Papertrail)

### Ongoing Maintenance:
- [ ] Monitor Render dashboard weekly
- [ ] Review security scan reports
- [ ] Update dependencies monthly
- [ ] Review and rotate secrets quarterly
- [ ] Monitor costs and usage
