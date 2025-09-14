# Render Deployment Guide

## Overview
Deploy the Currency Exchange Admin App to Render with automatic deployments from GitHub.

## Prerequisites
- GitHub Account with your repository
- Render Account (free tier available)
- Custom Domain (optional)

## Quick Setup

### 1. Repository Preparation
```bash
git add .
git commit -m "Initial commit: Currency Exchange Admin App"
git push origin main
```

### 2. Render Configuration
Create `render.yaml` in your repository root:

```yaml
services:
  - type: web
    name: currency-exchange
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn --bind 0.0.0.0:$PORT app:app"
    envVars:
      - key: FLASK_ENV
        value: production
      - key: DEBUG
        value: false
      - key: SECRET_KEY
        generateValue: true
      - key: ADMIN_USERNAME
        value: admin
      - key: ADMIN_PASSWORD
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: currency-exchange-db
          property: connectionString

databases:
  - name: currency-exchange-db
    databaseName: currency_exchange
    user: currency_user
```

### 3. Deploy to Render
1. Go to [render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure environment variables
5. Deploy automatically

### 4. Environment Variables
Set in Render dashboard:
```
FLASK_ENV=production
DEBUG=false
SECRET_KEY=[Auto-generated]
ADMIN_USERNAME=admin
ADMIN_PASSWORD=[Secure password]
DATABASE_URL=[Auto-configured]
```

### 5. Custom Domain (Optional)
1. Add domain in Render dashboard
2. Configure DNS CNAME to point to your-app.onrender.com
3. SSL certificate is provided automatically

## Automatic Deployments
- Push to main branch triggers automatic deployment
- Render handles build, migration, and deployment
- Monitor progress in Render dashboard

## Security Checklist
- [ ] Change default admin credentials
- [ ] Use strong SECRET_KEY
- [ ] Never commit secrets to repository
- [ ] Enable branch protection in GitHub
- [ ] Keep dependencies updated

## Troubleshooting
- Check deployment logs in Render dashboard
- Verify environment variables are set correctly
- Ensure requirements.txt includes all dependencies
- Test database connection

Your app will be available at `https://your-app-name.onrender.com`