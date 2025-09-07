# Docker Deployment Guide

## Overview

This guide covers deploying the Currency Exchange Admin App using Docker with environment-specific configurations and database migrations.

## Quick Start

### Development Deployment

```bash
# Clone the repository
git clone <repository-url>
cd currency-exchange

# Start development environment
docker-compose -f docker-compose.dev.yml up --build

# Access the application
open http://localhost:5001
```

### Production Deployment

```bash
# Update production environment variables
cp .env.production .env
# Edit .env with your production settings

# Start production environment
docker-compose up --build -d

# Access the application
open http://localhost:8000
```

## Environment Configuration

### Development Environment (`.env.development`)

```env
FLASK_ENV=development
DEBUG=true
PORT=5001
SECRET_KEY=dev-secret-key-change-in-production
LOAD_SAMPLE_DATA=true
DATABASE_URL=sqlite:///data/currency_exchange.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

### Production Environment (`.env.production`)

```env
FLASK_ENV=production
DEBUG=false
PORT=8000
SECRET_KEY=CHANGE-THIS-TO-A-SECURE-SECRET-KEY
LOAD_SAMPLE_DATA=false
DATABASE_URL=sqlite:///data/currency_exchange.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=CHANGE-THIS-PASSWORD
```

## Database Migrations

The application automatically runs database migrations on startup:

1. **Creates all database tables**
2. **Creates admin user** from environment variables
3. **Loads sample data** (only if `LOAD_SAMPLE_DATA=true`)

### Admin User Management

Admin users are created/updated via database migrations:

- **Username**: Set via `ADMIN_USERNAME` environment variable
- **Password**: Set via `ADMIN_PASSWORD` environment variable
- **Password Hashing**: Automatically handled using Werkzeug
- **Updates**: Password is updated if changed in environment variables

## Docker Commands

### Development

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up --build

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop environment
docker-compose -f docker-compose.dev.yml down

# Rebuild and restart
docker-compose -f docker-compose.dev.yml up --build --force-recreate
```

### Production

```bash
# Start production environment
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop environment
docker-compose down

# Update and restart
docker-compose pull
docker-compose up --build -d
```

### Database Management

```bash
# Access container shell
docker-compose exec currency-exchange /bin/bash

# Run migrations manually
docker-compose exec currency-exchange python migrations.py

# Backup database
docker-compose exec currency-exchange cp /app/data/currency_exchange.db /app/data/backup_$(date +%Y%m%d).db
```

## Custom DNS Setup with Docker

### Option 1: Reverse Proxy with Nginx

Create `nginx.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Update `docker-compose.yml`:

```yaml
version: '3.8'

services:
  currency-exchange:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - currency-exchange
    restart: unless-stopped
```

### Option 2: Traefik Reverse Proxy

Create `docker-compose.traefik.yml`:

```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=your-email@domain.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    restart: unless-stopped

  currency-exchange:
    build: .
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.currency-exchange.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.currency-exchange.entrypoints=websecure"
      - "traefik.http.routers.currency-exchange.tls.certresolver=myresolver"
      - "traefik.http.services.currency-exchange.loadbalancer.server.port=8000"
    restart: unless-stopped
```

## Production Security

### Environment Variables

```bash
# Generate secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Update .env.production
SECRET_KEY=your-generated-secret-key
ADMIN_USERNAME=your-admin-username
ADMIN_PASSWORD=your-secure-password
```

### SSL Certificate

```bash
# Using Let's Encrypt with Certbot
docker run -it --rm --name certbot \
  -v "${PWD}/ssl:/etc/letsencrypt" \
  -v "${PWD}/ssl-challenge:/var/www/certbot" \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
  -d your-domain.com
```

### Firewall Configuration

```bash
# Allow only necessary ports
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable
```

## Monitoring and Logging

### Docker Compose with Monitoring

```yaml
version: '3.8'

services:
  currency-exchange:
    build: .
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 30
    restart: unless-stopped
```

### Health Checks

```bash
# Check application health
curl -f http://localhost:8000/ || echo "Application is down"

# Check container status
docker-compose ps

# View container logs
docker-compose logs currency-exchange
```

## Backup and Recovery

### Automated Backup Script

Create `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker-compose exec -T currency-exchange cat /app/data/currency_exchange.db > $BACKUP_DIR/currency_exchange_$DATE.db

# Backup environment files
cp .env.production $BACKUP_DIR/env_production_$DATE

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "*.db" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/currency_exchange_$DATE.db"
```

### Recovery

```bash
# Stop application
docker-compose down

# Restore database
cp backups/currency_exchange_YYYYMMDD_HHMMSS.db data/currency_exchange.db

# Start application
docker-compose up -d
```

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Check what's using the port
   lsof -i :8000
   
   # Change port in .env file
   PORT=8001
   ```

2. **Permission denied on data directory**
   ```bash
   # Fix permissions
   sudo chown -R 1000:1000 data/
   ```

3. **Database migration fails**
   ```bash
   # Run migrations manually
   docker-compose exec currency-exchange python migrations.py
   ```

4. **Environment variables not loaded**
   ```bash
   # Check if .env file exists and is readable
   ls -la .env*
   
   # Verify environment variables in container
   docker-compose exec currency-exchange env | grep FLASK
   ```

### Logs and Debugging

```bash
# View application logs
docker-compose logs -f currency-exchange

# Access container shell
docker-compose exec currency-exchange /bin/bash

# Check environment variables
docker-compose exec currency-exchange env

# Test database connection
docker-compose exec currency-exchange python -c "from app import db; print(db.engine.url)"
```

## Performance Optimization

### Production Optimizations

1. **Use multi-stage Docker build**
2. **Enable Gunicorn worker processes**
3. **Configure proper logging levels**
4. **Use external database for scaling**

### Resource Limits

```yaml
services:
  currency-exchange:
    build: .
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

## Scaling

### Horizontal Scaling

```yaml
version: '3.8'

services:
  currency-exchange:
    build: .
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data
    deploy:
      replicas: 3
    restart: unless-stopped

  load-balancer:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    depends_on:
      - currency-exchange