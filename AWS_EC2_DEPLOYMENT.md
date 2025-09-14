# AWS EC2 Deployment Guide - Currency Exchange App

## Overview
Deploy your Currency Exchange app to AWS EC2 with minimal cost using free tier services.

**Cost**: Free for 12 months, then ~$28/month

---

## Prerequisites
- AWS Account with free tier eligibility
- Domain name (optional)
- SSH key pair

---

## Step 1: Create RDS Database

1. Go to **RDS Console** → **Create Database**
2. Configure:
   - **Engine**: PostgreSQL
   - **Template**: Free tier
   - **DB Instance**: db.t3.micro
   - **Storage**: 20 GB
   - **Database name**: `currency_exchange`
   - **Master username**: `currencyuser`
   - **Master password**: Create secure password
   - **Public access**: Yes
   - **Security group**: Create new (allow port 5432)

---

## Step 2: Launch EC2 Instance

1. Go to **EC2 Console** → **Launch Instance**
2. Configure:
   - **AMI**: Amazon Linux 2023
   - **Instance Type**: t2.micro (free tier)
   - **Key Pair**: Create new or use existing
   - **Security Group**: Create new with:
     - SSH (22) from your IP
     - HTTP (80) from anywhere
     - HTTPS (443) from anywhere

3. **Allocate Elastic IP** (recommended):
   - Go to **EC2** → **Elastic IPs** → **Allocate**
   - Associate with your instance

---

## Step 3: Automated Setup

### Connect to EC2:
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
```

### Run automated setup:
```bash
# Download deployment script
curl -O https://raw.githubusercontent.com/yourusername/currency-exchange/main/aws-deploy.sh
chmod +x aws-deploy.sh
./aws-deploy.sh
```

The script will prompt for:
- GitHub repository URL
- RDS endpoint and credentials
- Domain name (optional)

---

## Step 4: DNS & SSL Setup

### Configure DNS:
Point your domain's A record to your Elastic IP:
```
Type: A
Host: @
Value: Your-Elastic-IP
TTL: 3600
```

### Setup SSL Certificate:
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
sudo snap install --classic certbot
sudo certbot --nginx -d yourdomain.com
```

---

## Step 5: Access Application

Your app will be available at:
- **Domain**: `https://yourdomain.com`
- **IP**: `http://your-elastic-ip`

**Admin Credentials** (generated during setup):
- Username: `admin`
- Password: Check terminal output during setup

---

## Management

### Deploy Updates:
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
cd /opt/currency-exchange
./aws-deploy.sh
```

### View Logs:
```bash
sudo journalctl -u currency-exchange -f
```

### Restart Services:
```bash
sudo systemctl restart currency-exchange nginx
```

---

## Manual Setup (Alternative)

If you prefer manual setup:

### 1. Install Dependencies:
```bash
sudo yum update -y
sudo yum install -y python3.11 python3.11-pip git nginx postgresql15
```

### 2. Setup Application:
```bash
sudo mkdir -p /opt/currency-exchange
sudo chown ec2-user:ec2-user /opt/currency-exchange
cd /opt/currency-exchange
git clone https://github.com/yourusername/currency-exchange.git .

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment:
```bash
# Edit .env.aws with your RDS details
DATABASE_URL=postgresql://currencyuser:password@your-rds-endpoint:5432/currency_exchange
```

### 4. Setup Services:
```bash
# Create systemd service (the aws-deploy.sh script does this automatically)
sudo tee /etc/systemd/system/currency-exchange.service > /dev/null << 'EOF'
[Unit]
Description=Currency Exchange Flask App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/currency-exchange
Environment=PATH=/opt/currency-exchange/venv/bin
EnvironmentFile=/opt/currency-exchange/.env.aws
ExecStart=/opt/currency-exchange/venv/bin/gunicorn --bind 127.0.0.1:5001 --workers 3 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable currency-exchange

# Start the service now
sudo systemctl start currency-exchange

# Configure Nginx (the aws-deploy.sh script does this automatically)
sudo tee /etc/nginx/conf.d/currency-exchange.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable nginx to start on boot
sudo systemctl enable nginx

# Start nginx now
sudo systemctl start nginx
```

### 5. Run Migrations:
```bash
source venv/bin/activate
python migrations.py
```

---

## How Everything Works Together

### Architecture Overview
```
Internet → Route 53/DNS → EC2 Public IP → Nginx (Port 80/443) → Flask App (Port 5001) → PostgreSQL RDS
```

### Traffic Flow Explanation

1. **User Request**: User types your domain in browser
2. **DNS Resolution**: Route 53 or your DNS provider resolves domain to EC2 Elastic IP
3. **Nginx Receives Request**: Nginx listens on ports 80 (HTTP) and 443 (HTTPS)
4. **Reverse Proxy**: Nginx forwards request to Flask app running on localhost:5001
5. **Flask Processing**: Your Currency Exchange app processes the request
6. **Database Query**: Flask connects to RDS PostgreSQL database if needed
7. **Response Path**: Response travels back through the same path to user

### Component Roles

#### **Nginx (Web Server/Reverse Proxy)**
- **Purpose**: Acts as the front-facing web server

- **Why not just use Gunicorn directly?**
  
  **Option 1: Gunicorn Direct (What we could do)**
  ```bash
  # Gunicorn listening on port 80 directly
  gunicorn --bind 0.0.0.0:80 --workers 3 app:app
  ```
  
  **Option 2: Nginx + Gunicorn (What we actually do)**
  ```bash
  # Nginx on port 80 → Gunicorn on localhost:5001
  nginx (port 80) → gunicorn --bind 127.0.0.1:5001 app:app
  ```

- **Why Nginx is Better Than Direct Gunicorn**:
  
  **1. Security**
  - **Gunicorn direct**: Exposes Python app directly to internet attacks
  - **Nginx**: Acts as security barrier, filters malicious requests before they reach your app
  
  **2. Performance**
  - **Gunicorn**: Python-based, slower at handling static files and many connections
  - **Nginx**: C-based, extremely fast at serving static files and handling connections
  
  **3. SSL/HTTPS**
  - **Gunicorn**: No built-in SSL support, would need complex additional configuration
  - **Nginx**: Excellent SSL/TLS handling, easy Let's Encrypt integration
  
  **4. Connection Handling**
  - **Gunicorn**: Limited concurrent connections (~1000), can be overwhelmed by traffic spikes
  - **Nginx**: Can handle 10,000+ concurrent connections efficiently
  
  **5. Static Files**
  - **Gunicorn**: Serves CSS/JS/images through Python (very slow)
  - **Nginx**: Serves static files directly from disk (lightning fast)
  
  **6. Request Buffering**
  - **Gunicorn**: Slow clients can tie up worker processes while uploading
  - **Nginx**: Buffers requests, only sends complete requests to Gunicorn
  
  **7. Graceful Error Handling**
  - **Gunicorn**: Can crash or hang under heavy load, taking down your site
  - **Nginx**: Gracefully handles errors, can retry failed requests, shows custom error pages

- **Real-world Performance Example**:
  ```
  Without Nginx: 100 concurrent users → Gunicorn (3 workers) → Potential bottleneck/crashes
  With Nginx: 1000 concurrent users → Nginx → Gunicorn (3 workers) → Smooth handling
  ```

- **Production Benefits**:
  - **Industry Standard**: Every major web application uses this pattern
  - **Easy Scaling**: Can add load balancing, caching, compression with simple config changes
  - **Multiple Apps**: Can serve multiple applications on same server
  - **Monitoring**: Better logging and monitoring capabilities

#### **systemd Service (Process Manager)**
- **Purpose**: Manages your Flask application as a Linux service
- **Why needed**:
  - Ensures app starts automatically on server boot
  - Automatically restarts app if it crashes
  - Provides standardized way to start/stop/monitor app
  - Manages process lifecycle and logging
- **Service File Location**: `/etc/systemd/system/currency-exchange.service`
- **Key Features**:
  - **Auto-restart**: `Restart=always` ensures app restarts on failure
  - **Environment**: Loads `.env.aws` file for configuration
  - **User Management**: Runs as `ec2-user` for security
  - **Dependency Management**: Starts after network is available

#### **Flask Application (Your App)**
- **Purpose**: The actual Currency Exchange application
- **Port**: Runs on localhost:5001 (not directly accessible from internet)
- **Process**: Managed by Gunicorn WSGI server with 3 worker processes
- **Security**: Only accessible through Nginx reverse proxy

#### **PostgreSQL RDS (Database)**
- **Purpose**: Stores currency data, admin users, and application state
- **Connection**: Flask connects using DATABASE_URL from `.env.aws`
- **Security**: Accessible only from EC2 security group

### Service Lifecycle

#### **Boot Process**:
1. EC2 instance starts
2. systemd loads all enabled services
3. `currency-exchange.service` starts automatically
4. Gunicorn launches Flask app with 3 workers
5. Nginx starts and begins listening for requests
6. App is ready to serve traffic

#### **Request Processing**:
1. Nginx receives HTTP request on port 80
2. Nginx checks its configuration (`/etc/nginx/conf.d/currency-exchange.conf`)
3. Request matches location `/` rule
4. Nginx forwards request to `http://127.0.0.1:5001`
5. Flask app processes request (may query database)
6. Flask returns response to Nginx
7. Nginx returns response to user

#### **Failure Recovery**:
- If Flask app crashes: systemd automatically restarts it (RestartSec=3)
- If Nginx crashes: systemd restarts Nginx
- If EC2 reboots: Both services start automatically on boot

### Security Model

#### **Network Security**:
- **Public Access**: Only ports 22 (SSH), 80 (HTTP), 443 (HTTPS) are open
- **Flask App**: Runs on localhost:5001, not accessible from internet
- **Database**: RDS security group only allows access from EC2

#### **Process Security**:
- **Non-root User**: Flask app runs as `ec2-user`, not root
- **Environment Variables**: Sensitive data in `.env.aws`, not in code
- **SSL/TLS**: Nginx handles HTTPS encryption

### Why This Architecture?

#### **Separation of Concerns**:
- **Nginx**: Handles web server tasks (SSL, static files, load balancing)
- **Flask**: Handles application logic
- **systemd**: Handles process management
- **RDS**: Handles database operations

#### **Scalability**:
- Can easily add more EC2 instances behind a load balancer
- Nginx can serve multiple Flask workers
- Database is separate and can be scaled independently

#### **Reliability**:
- Multiple layers of failure recovery
- Each component can be restarted independently
- Automatic service recovery on system reboot

#### **Maintainability**:
- Clear separation makes debugging easier
- Standard Linux service management
- Configuration files are well-organized

---

## Understanding systemctl Process

### systemd vs. Kubernetes: Native Linux Process Management

**Yes, systemd is the native Linux alternative to container orchestration like Kubernetes.**

#### **systemd (What we use)**
- **Native Linux**: Built into every modern Linux distribution
- **Process Management**: Manages processes directly on the host OS
- **Scope**: Single machine process orchestration
- **Resource Usage**: Minimal overhead, no containers
- **Complexity**: Simple configuration files

#### **Kubernetes (Alternative approach)**
- **Container Orchestration**: Manages containerized applications across clusters
- **Scope**: Multi-machine cluster orchestration
- **Resource Usage**: Higher overhead (containers, pods, nodes)
- **Complexity**: Complex YAML configurations, learning curve

#### **When to use each:**

**Use systemd (our approach) when:**
- Single server deployment
- Simple application architecture
- Minimal resource overhead needed
- Direct OS integration preferred
- Cost optimization important

**Use Kubernetes when:**
- Multi-server clusters
- Microservices architecture
- Auto-scaling across machines
- Complex deployment patterns
- Container-first approach

#### **For Currency Exchange App:**

**How do we determine it's monolithic vs microservices?**

**Analyzing the app.py structure:**
```python
# Single Flask application file (app.py) contains:
- Web routes (/login, /dashboard, /add_currency, etc.)
- Database models (AdminUser, Currency)
- Authentication logic
- Business logic (currency calculations)
- All functionality in one codebase
```

**Monolithic Architecture Indicators:**
1. **Single Deployment Unit**: Everything deployed as one Flask app
2. **Shared Database**: All features use the same PostgreSQL database
3. **Single Process**: One Gunicorn process serves all functionality
4. **Tight Coupling**: Authentication, currency management, and UI in same codebase
5. **Single Technology Stack**: All Python/Flask

**If it were Microservices, we'd see:**
```
- auth-service (handles login/logout)
- currency-service (manages currency data)
- calculation-service (handles conversions)
- ui-service (frontend)
- Each with separate databases
- API communication between services
```

**Why systemd works perfectly for this monolithic app:**
- **Single Service**: One systemd service manages the entire application
- **Simple Deployment**: Deploy everything together as one unit
- **Shared Resources**: All components share same database connection
- **Cost-effective**: No container overhead or service mesh complexity
- **Easy Debugging**: All logs in one place, single point of failure

**When you'd need Kubernetes instead:**
- If you split into separate services (auth-service, currency-service, etc.)
- If you needed independent scaling of different features
- If different teams owned different parts of the application
- If you needed different technology stacks for different features

**Current Architecture Decision:**
For a currency exchange admin tool with ~5-10 routes and simple CRUD operations, monolithic architecture with systemd is the right choice - it's simpler, cheaper, and easier to maintain.

---

The deployment uses **systemd** to manage your Flask application as a Linux service:

### Key systemctl Commands:
```bash
# Check service status
sudo systemctl status currency-exchange

# Start the service
sudo systemctl start currency-exchange

# Stop the service
sudo systemctl stop currency-exchange

# Restart the service
sudo systemctl restart currency-exchange

# Enable service to start on boot
sudo systemctl enable currency-exchange

# Disable service from starting on boot
sudo systemctl disable currency-exchange

# Reload systemd configuration after changes
sudo systemctl daemon-reload
```

### What happens during deployment:
1. **Service Creation**: A systemd service file is created at `/etc/systemd/system/currency-exchange.service`
2. **Daemon Reload**: `systemctl daemon-reload` tells systemd to recognize the new service
3. **Enable Service**: `systemctl enable` creates symlinks so the service starts automatically on boot
4. **Start Service**: `systemctl start` immediately starts your Flask application
5. **Nginx Setup**: Nginx is configured as a reverse proxy to forward requests to your Flask app

### Service Benefits:
- **Auto-restart**: Service automatically restarts if it crashes
- **Boot persistence**: Service starts automatically when server reboots
- **Log management**: Logs are managed by systemd and viewable with `journalctl`
- **Process management**: systemd handles process lifecycle

---

## Troubleshooting

### Service Issues:
```bash
sudo systemctl status currency-exchange
sudo journalctl -u currency-exchange -n 50
```

### Database Connection:
```bash
psql -h your-rds-endpoint -U currencyuser -d currency_exchange
```

### Nginx Issues:
```bash
sudo nginx -t
sudo systemctl status nginx
```

---

## Security Checklist

- [ ] Change default admin password
- [ ] Restrict SSH to your IP only
- [ ] Enable HTTPS with SSL certificate
- [ ] Configure automated backups
- [ ] Set up CloudWatch monitoring

Your Currency Exchange app is now running on AWS EC2!