# Awaz Pipeline — Deployment Guide

This guide covers deploying the Awaz multi-agent intelligence pipeline to production.

---

## Deployment Options

### Option 1: Railway (Recommended for Quick Deployment)

Railway is the easiest option for deploying the backend + web frontend together.

**Pros:** Free tier available, automatic SSL, built-in PostgreSQL, easy GitHub integration
**Cons:** Limited resources on free tier

### Option 2: Render

Render is another excellent option with similar benefits to Railway.

**Pros:** Free tier available, automatic SSL, easy deployment
**Cons:** Cold starts on free tier

### Option 3: Self-hosted VPS (AWS/GCP/Azure/DigitalOcean)

For full control and production-grade deployment.

**Pros:** Full control, no cold starts, scalable
**Cons:** Requires DevOps knowledge, manual SSL setup

---

## Option 1: Deploy to Railway

### Step 1: Prepare Your Repository

1. Push your code to GitHub
2. Ensure `.env.example` is in the repo (but NOT `.env`)
3. Ensure `Dockerfile` and `.dockerignore` are in the repo

### Step 2: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway will detect the Dockerfile automatically

### Step 3: Configure Environment Variables

In Railway dashboard, add these variables:

```
AWAZ_HOST=0.0.0.0
AWAZ_PORT=5050
GEMINI_API_KEY=your_actual_key
HF_API_KEY=your_actual_key
NEWSAPI_KEY=your_actual_key
REDDIT_CLIENT_ID=your_actual_id
REDDIT_CLIENT_SECRET=your_actual_secret
REDDIT_USER_AGENT=awaz-intelligence-pipeline/1.0
EXCHANGE_RATE_API_KEY=your_actual_key
WHISPER_MODEL=base
```

### Step 4: Deploy

1. Click "Deploy"
2. Railway will build the Docker image and deploy
3. Once deployed, Railway will provide a public URL
4. Access your app at `https://your-project.railway.app`

---

## Option 2: Deploy to Render

### Step 1: Prepare Your Repository

Same as Railway steps above.

### Step 2: Create Render Service

1. Go to [render.com](https://render.com)
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Runtime**: Docker
   - **Dockerfile Path**: `./Dockerfile`
   - **Context**: `./`

### Step 3: Configure Environment Variables

Add the same environment variables as Railway.

### Step 4: Deploy

1. Click "Create Web Service"
2. Render will build and deploy
3. Access at `https://your-service.onrender.com`

---

## Option 3: Self-Hosted VPS

### Prerequisites

- VPS with Ubuntu 20.04+ (DigitalOcean, AWS EC2, GCP, etc.)
- Domain name (optional, for HTTPS)
- At least 2GB RAM, 2 vCPU

### Step 1: Server Setup

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose -y

# Install Nginx
sudo apt install nginx -y
```

### Step 2: Deploy Application

```bash
# Clone your repository
git clone https://github.com/your-username/awaz-pipeline.git
cd awaz-pipeline

# Create .env file
cp .env.example .env
nano .env  # Add your actual API keys

# Build and run with Docker Compose
docker-compose up -d
```

### Step 3: Configure Nginx (Optional, for Domain + SSL)

```bash
# Create Nginx config
sudo nano /etc/nginx/sites-available/awaz

# Add this configuration:
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5050;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /socket.io {
        proxy_pass http://localhost:5050;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/awaz /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Install SSL with Certbot
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

---

## Mobile App Deployment

### Build APK for Distribution

```powershell
cd d:\Hackathon\Launchmind-Agentic\mobile_flutter

# Build release APK
C:\src\flutter\bin\flutter.bat build apk --release

# Output: build/app/outputs/flutter-apk/app-release.apk
```

### Build App Bundle for Google Play

```powershell
# Build release AAB
C:\src\flutter\bin\flutter.bat build appbundle --release

# Output: build/app/outputs/bundle/release/app-release.aab
```

### Distribute APK

1. Upload APK to a file hosting service (Google Drive, Dropbox, etc.)
2. Share the download link
3. Users download and install (requires "Allow unknown sources" in Android settings)

### Publish to Google Play Store

1. Create Google Play Console account ($25 one-time fee)
2. Create new app
3. Upload app-release.aab
4. Fill in store listing, screenshots, privacy policy
5. Submit for review

---

## Production Checklist

- [ ] All API keys are set as environment variables (never in code)
- [ ] `.env` is in `.gitignore`
- [ ] Database is configured (if using persistent storage)
- [ ] SSL/HTTPS is enabled
- [ ] Error logging is configured
- [ ] Rate limiting is implemented (for API endpoints)
- [ ] Health check endpoint is available
- [ ] Backup strategy is in place
- [ ] Monitoring/alerting is set up

---

## Environment Variables for Production

| Variable | Required | Description |
|----------|----------|-------------|
| `AWAZ_HOST` | Yes | Bind address (use `0.0.0.0`) |
| `AWAZ_PORT` | Yes | Port (default `5050`) |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `HF_API_KEY` | No | HuggingFace fallback |
| `NEWSAPI_KEY` | Yes | NewsAPI key |
| `REDDIT_CLIENT_ID` | Yes | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Yes | Reddit app client secret |
| `REDDIT_USER_AGENT` | Yes | Reddit user agent string |
| `EXCHANGE_RATE_API_KEY` | Yes | Exchange rate API key |
| `WHISPER_MODEL` | No | Whisper model size (default: `base`) |
| `SLACK_WEBHOOK_URL` | No | Slack webhook for alerts |

---

## Troubleshooting Deployment

### Railway/Render Build Failures

- Check Dockerfile syntax
- Ensure all dependencies are in `requirements.txt`
- Verify `.dockerignore` doesn't exclude necessary files

### Socket.io Connection Issues

- Ensure WebSocket support is enabled in reverse proxy
- Check that `AWAZ_HOST` is set to `0.0.0.0`
- Verify port forwarding is correct

### Mobile App Can't Connect to Backend

- Use your deployed backend URL in `AWAZ_BASE_URL`
- Ensure CORS is configured correctly
- Check that the backend is accessible from the internet

---

## Scaling Considerations

### Backend Scaling

- Use a load balancer (nginx, HAProxy)
- Deploy multiple instances behind the load balancer
- Use Redis for Socket.io scaling (if needed)
- Consider a message queue (RabbitMQ, Redis) for background tasks

### Database Scaling

- Use managed database services (Railway PostgreSQL, Render PostgreSQL)
- Implement connection pooling
- Add read replicas for read-heavy workloads

---

## Monitoring & Logging

### Application Monitoring

- Use services like Sentry for error tracking
- Implement health check endpoint: `/health`
- Monitor resource usage (CPU, memory, disk)

### Log Aggregation

- Use services like Logtail, Papertrail, or AWS CloudWatch
- Ensure logs include timestamps and correlation IDs
- Set up alerts for critical errors

---

## Cost Estimates

### Railway Free Tier
- $0/month (500 hours compute, 500MB storage)
- Suitable for development/testing

### Railway Paid
- ~$5-20/month depending on usage
- Recommended for production

### Render Free Tier
- $0/month (with cold starts)
- Suitable for low-traffic apps

### VPS (DigitalOcean)
- $6-20/month depending on specs
- Full control, no cold starts

---

## Next Steps

1. Choose your deployment platform (Railway recommended for quick start)
2. Push code to GitHub
3. Configure environment variables
4. Deploy and test
5. Set up monitoring and alerts
6. Deploy mobile app APK for distribution
