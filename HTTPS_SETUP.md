# HTTPS Setup Guide for AWS EC2

## Prerequisites Checklist
- [ ] EC2 instance running with Elastic IP configured
- [ ] Domain name purchased and accessible
- [ ] SSH access to EC2 instance
- [ ] Currency Exchange app deployed and running on HTTP

## Step 1: Configure DNS
- [ ] Log into your domain registrar (GoDaddy, Namecheap, Cloudflare, etc.)
- [ ] Create A record pointing to your Elastic IP:
  ```
  Type: A
  Name: @ (or your subdomain)
  Value: YOUR_ELASTIC_IP
  TTL: 3600
  ```
- [ ] Optional: Create CNAME for www subdomain:
  ```
  Type: CNAME
  Name: www
  Value: yourdomain.com
  TTL: 3600
  ```
- [ ] Wait 5-10 minutes for DNS propagation
- [ ] Verify DNS works: `nslookup yourdomain.com`

## Step 2: Update Security Group
- [ ] Go to AWS Console → EC2 → Security Groups
- [ ] Select your instance's security group
- [ ] Add inbound rules:
  ```
  Type: HTTP, Port: 80, Source: 0.0.0.0/0
  Type: HTTPS, Port: 443, Source: 0.0.0.0/0
  Type: SSH, Port: 22, Source: YOUR_IP/32
  ```
- [ ] Save rules

## Step 3: Install Certbot
- [ ] SSH into your EC2 instance:
  ```bash
  ssh -i your-key.pem ec2-user@your-elastic-ip
  ```
- [ ] Install Certbot:
  ```bash
  sudo snap install --classic certbot
  ```
- [ ] Create symlink for easier access:
  ```bash
  sudo ln -s /snap/bin/certbot /usr/bin/certbot
  ```

## Step 4: Generate SSL Certificate
- [ ] Run Certbot to automatically configure Nginx:
  ```bash
  sudo certbot --nginx -d yourdomain.com
  ```
- [ ] If you have www subdomain:
  ```bash
  sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
  ```
- [ ] Follow prompts:
  - [ ] Enter email address for renewal notifications
  - [ ] Agree to terms of service
  - [ ] Choose whether to share email with EFF (optional)
  - [ ] Select redirect option (recommended: redirect HTTP to HTTPS)

## Step 5: Verify Configuration
- [ ] Test Nginx configuration:
  ```bash
  sudo nginx -t
  ```
- [ ] Reload Nginx if test passes:
  ```bash
  sudo systemctl reload nginx
  ```
- [ ] Test HTTPS access:
  ```bash
  curl -I https://yourdomain.com
  ```
- [ ] Visit your site in browser: `https://yourdomain.com`
- [ ] Verify SSL certificate shows as valid (green lock icon)

## Step 6: Test Auto-Renewal
- [ ] Check if renewal timer is active:
  ```bash
  sudo systemctl status snap.certbot.renew.timer
  ```
- [ ] Test renewal process (dry run):
  ```bash
  sudo certbot renew --dry-run
  ```
- [ ] Verify no errors in dry run output

## Step 7: Final Verification
- [ ] Test HTTP redirect: Visit `http://yourdomain.com` → should redirect to HTTPS
- [ ] Test HTTPS direct: Visit `https://yourdomain.com` → should load securely
- [ ] Check certificate details in browser (click lock icon)
- [ ] Verify certificate is valid for 90 days
- [ ] Test your Currency Exchange app functionality over HTTPS

## Troubleshooting Checklist

### If DNS doesn't resolve:
- [ ] Check DNS propagation: `dig yourdomain.com`
- [ ] Wait longer (DNS can take up to 24 hours)
- [ ] Verify A record points to correct Elastic IP

### If Certbot fails:
- [ ] Ensure domain resolves to your server: `nslookup yourdomain.com`
- [ ] Check port 80 is accessible: `curl -I http://yourdomain.com`
- [ ] Verify Nginx is running: `sudo systemctl status nginx`
- [ ] Check Nginx configuration: `sudo nginx -t`

### If HTTPS doesn't work:
- [ ] Check security group allows port 443
- [ ] Verify certificate files exist: `sudo ls /etc/letsencrypt/live/yourdomain.com/`
- [ ] Check Nginx SSL configuration: `sudo cat /etc/nginx/conf.d/currency-exchange.conf`
- [ ] Review Nginx error logs: `sudo tail -f /var/log/nginx/error.log`

## Maintenance Tasks

### Monthly:
- [ ] Check certificate expiration: `sudo certbot certificates`
- [ ] Verify auto-renewal is working: `sudo systemctl status snap.certbot.renew.timer`

### Before Certificate Expires (Let's Encrypt sends email reminders):
- [ ] Manual renewal if auto-renewal fails: `sudo certbot renew`
- [ ] Reload Nginx after renewal: `sudo systemctl reload nginx`

## Expected Results
After completing all steps:
- ✅ `http://yourdomain.com` → Redirects to HTTPS
- ✅ `https://yourdomain.com` → Loads securely with valid certificate
- ✅ Browser shows green lock icon
- ✅ Certificate auto-renews every 60 days
- ✅ Your Currency Exchange app is accessible via secure HTTPS

## Security Benefits Achieved
- 🔒 **Encrypted traffic** between users and your server
- 🛡️ **Protection against man-in-the-middle attacks**
- ✅ **Browser trust indicators** (green lock)
- 📱 **Mobile compatibility** (modern browsers require HTTPS)
- 🚀 **SEO benefits** (Google favors HTTPS sites)
- 💳 **Payment security** (required for payment processing)

Your Currency Exchange app is now production-ready with enterprise-grade security!