# Deployment Guide - Render

## Quick Deploy to Render

### Prerequisites
1. Push code to GitHub repository
2. Have Stripe API keys ready
3. Have Google Cloud service account credentials

### Render Setup

1. **Connect Repository**
   - Go to [Render Dashboard](https://render.com)
   - Click "New" → "Web Service"
   - Connect your GitHub repository

2. **Configure Service**
   - **Name**: `aiviralcontent-backend`
   - **Region**: Oregon (US West)
   - **Branch**: `main`
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && python start.py`

3. **Environment Variables**
   Set these in Render dashboard:
   ```
   STRIPE_SECRET_KEY=sk_live_... (or sk_test_... for testing)
   GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp-service-account.json
   GOOGLE_CLOUD_PROJECT=gothic-guard-459415-q5
   ENVIRONMENT=production
   PORT=10000
   ```

4. **Google Cloud Service Account**
   - Upload your service account JSON file as a secret file
   - Mount it at `/etc/secrets/gcp-service-account.json`

### Health Check
- Health endpoint: `/health`
- Should return: `{"status": "healthy"}`

### API Endpoints
- `GET /` - API info
- `GET /health` - Health check
- `POST /generate-titles` - Generate title suggestions
- `GET /generate-gemini` - Generate content with Gemini AI
- `POST /create-checkout-session` - Create Stripe checkout
- `GET /test-env` - Check environment variables

### Troubleshooting
1. Check logs in Render dashboard
2. Verify environment variables are set
3. Ensure service account has proper permissions
4. Test endpoints individually

### Production URL
Your API is available at: `https://aiviralcontent-api.onrender.com`

### Updating Existing Service
Since your service already exists:

1. **Push Updated Code**
   ```bash
   git add .
   git commit -m "Update backend for production deployment"
   git push origin main
   ```

2. **Render will auto-deploy** if auto-deploy is enabled
   - Or manually trigger deployment from Render dashboard

3. **Verify Deployment**
   - Check health: `https://aiviralcontent-api.onrender.com/health`
   - Should return: `{"status": "healthy"}`

### Quick Fix Commands
If the deployment fails, check these in Render dashboard:
- Build Command: `cd backend && pip install -r requirements.txt`  
- Start Command: `cd backend && python start.py`
- Health Check Path: `/health`