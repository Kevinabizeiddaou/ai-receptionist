# Deployment Guide - Mounir Cutzz AI Receptionist

This guide covers deploying the AI phone receptionist system to various platforms.

## 🚀 Quick Deploy Options

### Option 1: Render (Recommended)

\`\`\`bash

# 1. Push code to GitHub

git add .
git commit -m "Initial commit"
git push origin main

# 2. Connect to Render

# - Go to render.com

# - Connect your GitHub repo

# - Use render.yaml for automatic configuration

# 3. Set environment variables in Render dashboard

\`\`\`

### Option 2: Railway

\`\`\`bash

# 1. Install Railway CLI

npm install -g @railway/cli

# 2. Deploy

railway login
railway init
railway up
\`\`\`

### Option 3: Docker

\`\`\`bash

# 1. Build and run

docker build -f Dockerfile.prod -t mounir-cutzz-ai .
docker run -d --env-file .env -p 8000:8000 mounir-cutzz-ai
\`\`\`

## 📋 Environment Variables

Required variables for all deployments:

\`\`\`bash

# Twilio Configuration

TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_phone_number

# OpenAI Configuration

OPENAI_API_KEY=your_openai_key

# Google Calendar

GOOGLE_CALENDAR_ID=your_calendar_id
GOOGLE_CREDENTIALS_JSON=your_service_account_json

# AWS (Optional - for enhanced TTS)

AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1

# Redis (Auto-configured on most platforms)

REDIS_URL=redis://localhost:6379
\`\`\`

## 🔧 Platform-Specific Setup

### Render Setup

1. **Connect Repository**: Link your GitHub repo to Render
2. **Environment**: Set to Python 3.11
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Add Redis**: Create a Redis service and link it

### Railway Setup

1. **Connect Repository**: Use Railway CLI or web dashboard
2. **Environment Variables**: Set in Railway dashboard
3. **Redis**: Add Redis plugin from Railway marketplace

### Heroku Setup

\`\`\`bash

# Create app

heroku create mounir-cutzz-ai-receptionist

# Add Redis

heroku addons:create heroku-redis:mini

# Set environment variables

heroku config:set TWILIO_ACCOUNT_SID=your_sid
heroku config:set TWILIO_AUTH_TOKEN=your_token

# ... (set all other variables)

# Deploy

git push heroku main
\`\`\`

## 📞 Twilio Configuration

After deployment, configure your Twilio phone number:

1. **Webhook URL**: `https://your-domain.com/webhook/voice`
2. **HTTP Method**: POST
3. **Status Callback**: `https://your-domain.com/webhook/status`

### Twilio Console Steps:

1. Go to Phone Numbers → Manage → Active numbers
2. Click your phone number
3. Set Voice webhook URL
4. Set Status callback URL
5. Save configuration

## 🔍 Health Checks & Monitoring

### Health Check Endpoint

\`\`\`bash
curl https://your-domain.com/
\`\`\`

Expected response:
\`\`\`json
{
"status": "healthy",
"service": "Mounir Cutzz AI Receptionist",
"features": {
"ai_agent": true,
"calendar_integration": true,
"speech_processing": true,
"session_management": true
}
}
\`\`\`

### Monitoring Logs

- **Render**: View logs in dashboard
- **Railway**: `railway logs`
- **Heroku**: `heroku logs --tail`
- **Docker**: `docker logs container_name`

## 🛠 Troubleshooting

### Common Issues

1. **Redis Connection Failed**

   - Ensure Redis service is running
   - Check REDIS_URL environment variable

2. **Google Calendar API Errors**

   - Verify service account JSON is valid
   - Check calendar ID and permissions

3. **Twilio Webhook Timeouts**

   - Ensure app responds within 10 seconds
   - Check server resources and scaling

4. **Speech Processing Issues**
   - Verify OpenAI API key
   - Check AWS credentials for Polly

### Debug Mode

Set environment variable for detailed logging:
\`\`\`bash
export LOG_LEVEL=DEBUG
\`\`\`

## 📊 Performance Optimization

### Scaling Recommendations

- **Render**: Use Standard plan for production
- **Railway**: Enable autoscaling
- **Heroku**: Use Standard dynos with multiple workers

### Redis Configuration

\`\`\`bash

# For high traffic, use Redis with persistence

REDIS_MAXMEMORY_POLICY=allkeys-lru
\`\`\`

## 🔒 Security Checklist

- [ ] All API keys stored as environment variables
- [ ] Twilio webhook signature validation enabled
- [ ] HTTPS enforced for all endpoints
- [ ] Redis password protection (if applicable)
- [ ] Regular security updates

## 📈 Cost Estimation (Monthly)

### Render + Redis

- Web Service: $7/month
- Redis: $7/month
- **Total**: ~$14/month

### Railway

- Starter Plan: $5/month
- Redis Plugin: $5/month
- **Total**: ~$10/month

### Heroku

- Basic Dyno: $7/month
- Redis Mini: $3/month
- **Total**: ~$10/month

_Plus usage costs for Twilio, OpenAI, and AWS services_

## 🎯 Production Checklist

- [ ] Environment variables configured
- [ ] Twilio webhook URL set
- [ ] Google Calendar integration tested
- [ ] Redis connection verified
- [ ] Health checks passing
- [ ] Phone number tested end-to-end
- [ ] Monitoring and alerts configured
- [ ] Backup and recovery plan in place
      \`\`\`

```json file="" isHidden

```
