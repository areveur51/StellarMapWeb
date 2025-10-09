# Linode VPS Deployment Guide - Hybrid Architecture

This guide walks you through deploying the **BigQuery cron job service** on Linode VPS while using **Replit Autoscale** for the web application.

## 🏗️ Hybrid Architecture Overview

![Hybrid Architecture](./diagrams/06_hybrid_architecture.png)

**Why This Architecture?**
- ✅ **Cost-Effective**: Replit Autoscale scales to zero when idle (~$5-15/month)
- ✅ **Reliable Cron Jobs**: Linode VPS runs 24/7 for BigQuery pipeline ($5-12/month)
- ✅ **Auto-Scaling Web**: Handle traffic spikes without managing infrastructure
- ✅ **Predictable Costs**: Fixed VPS cost + variable Replit costs
- ✅ **DDoS Protected**: Cloudflare free tier provides unlimited DDoS protection

---

## Part 1: Linode VPS Setup

### Step 1: Create Linode Instance

1. **Sign up/Login** to [Linode](https://www.linode.com/)

2. **Create Linode** (Click "Create" → "Linode"):
   - **Image**: Ubuntu 24.04 LTS (recommended)
   - **Region**: Choose closest to your users (e.g., Newark, NJ or Frankfurt, DE)
   - **Plan**: 
     - **Shared CPU - Nanode 1GB** ($5/month) - Sufficient for cron jobs
     - **Shared CPU - Linode 2GB** ($12/month) - Recommended for better performance
   - **Label**: `stellarmapweb-cron`
   - **Root Password**: Strong password (save it securely)
   - **SSH Keys**: Add your SSH public key (highly recommended)

3. **Click "Create Linode"** and wait ~30 seconds for provisioning

4. **Note your IP address** (shown in dashboard)

### Step 2: Initial Server Setup

**SSH into your server:**
```bash
ssh root@YOUR_LINODE_IP
```

**Update the system:**
```bash
apt update && apt upgrade -y
```

**Create a non-root user:**
```bash
# Create user
adduser stellarmap

# Add to sudo group
usermod -aG sudo stellarmap

# Switch to new user
su - stellarmap
```

**Set up firewall:**
```bash
# Allow SSH
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable

# Verify
sudo ufw status
```

### Step 3: Install Docker & Docker Compose

**Install Docker:**
```bash
# Install prerequisites
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker stellarmap

# Log out and back in for group changes to take effect
exit
```

**Log back in as stellarmap user:**
```bash
ssh stellarmap@YOUR_LINODE_IP
```

**Verify Docker installation:**
```bash
docker --version
docker compose version
```

---

## Part 2: Deploy BigQuery Cron Service

### Step 1: Clone Repository

```bash
# Create application directory
mkdir -p ~/apps
cd ~/apps

# Clone your repository (replace with your repo URL)
git clone https://github.com/yourusername/StellarMapWeb.git
cd StellarMapWeb
```

**Or upload files via SCP:**
```bash
# From your local machine
scp -r ./StellarMapWeb stellarmap@YOUR_LINODE_IP:~/apps/
```

### Step 2: Create Environment File

```bash
# Create .env file
nano .env
```

**Add the following variables:**
```bash
# Django
DJANGO_SETTINGS_MODULE=StellarMapWeb.settings
DJANGO_SECRET_KEY=your-production-secret-key-here

# Astra DB (Cassandra)
CASSANDRA_DB_NAME=stellarmapweb
CASSANDRA_KEYSPACE=stellarmapweb
ASTRA_DB_ID=your-astra-db-id
ASTRA_DB_REGION=your-region
ASTRA_DB_TOKEN=your-astra-token
ASTRA_DB_APPLICATION_TOKEN=your-app-token
ASTRA_DB_CLIENT_ID=your-client-id
ASTRA_DB_SECRET=your-secret

# Google BigQuery
GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account","project_id":"..."}' 

# Sentry (optional)
SENTRY_DSN=your-sentry-dsn

# Cron Schedule
CRON_INTERVAL_MINUTES=60
```

**Save and exit** (Ctrl+X, Y, Enter)

**Secure the file:**
```bash
chmod 600 .env
```

### Step 3: Create Cron-Only Docker Compose

The VPS only needs to run the BigQuery cron job (no web server).

```bash
nano docker-compose.cron.yml
```

**Add this configuration:**
```yaml
version: '3.8'

services:
  # BigQuery cron job (runs every hour)
  bigquery_cron:
    build: .
    container_name: stellarmapweb_cron
    command: >
      sh -c "while true; do
        echo '[$(date)] Starting BigQuery pipeline...';
        python manage.py bigquery_pipeline --limit 100;
        echo '[$(date)] Pipeline completed. Sleeping for ${CRON_INTERVAL_MINUTES:-60} minutes...';
        sleep $((${CRON_INTERVAL_MINUTES:-60} * 60));
      done"
    env_file:
      - .env
    environment:
      - DJANGO_SETTINGS_MODULE=StellarMapWeb.settings
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"
```

**Save and exit**

### Step 4: Build and Start Service

```bash
# Build the image
docker compose -f docker-compose.cron.yml build

# Start the service
docker compose -f docker-compose.cron.yml up -d

# Verify it's running
docker compose -f docker-compose.cron.yml ps

# Check logs
docker compose -f docker-compose.cron.yml logs -f bigquery_cron
```

**You should see:**
```
[2025-01-09 14:30:00] Starting BigQuery pipeline...
✅ Processing pending accounts...
✅ Pipeline completed. Sleeping for 60 minutes...
```

---

## Part 3: Replit Autoscale Configuration

### Step 1: Configure Deployment in Replit

In your Replit project, you already have the deployment configured. Let me verify:

**Check `.replit` file** or use deployment config tool to ensure:
- **Deployment target**: `autoscale`
- **Run command**: Gunicorn for production

### Step 2: Set Environment Variables in Replit

**Go to Replit → Secrets** and add:
```
DJANGO_SETTINGS_MODULE=StellarMapWeb.production
DJANGO_SECRET_KEY=<same-as-linode>
CASSANDRA_DB_NAME=stellarmapweb
CASSANDRA_KEYSPACE=stellarmapweb
ASTRA_DB_ID=<your-id>
ASTRA_DB_REGION=<your-region>
ASTRA_DB_TOKEN=<your-token>
... (all Astra DB credentials)
SENTRY_DSN=<your-sentry-dsn>
```

**Important:** Do NOT include `GOOGLE_APPLICATION_CREDENTIALS_JSON` in Replit (BigQuery only runs on Linode VPS)

### Step 3: Deploy to Replit Autoscale

1. Click **Deploy** button in Replit
2. Choose **Autoscale Deployment**
3. Configure:
   - **Max machines**: 10 (adjust based on expected traffic)
   - **Region**: Choose closest to users
4. Click **Deploy**

---

## Part 4: Cloudflare Setup

### Step 1: Point Domain to Replit

1. **Get Replit deployment URL** (e.g., `stellarmapweb-username.repl.co`)

2. **Add DNS records in Cloudflare:**
   ```
   Type: CNAME
   Name: @
   Target: stellarmapweb-username.repl.co
   Proxy: ON (Orange Cloud)
   ```

3. **SSL/TLS Settings:**
   - Mode: **Full** (Replit handles SSL)
   - Always Use HTTPS: **ON**

### Step 2: Configure Firewall Rules (Optional)

**Protect against DDoS:**
```
Rule 1: Rate limit
- Expression: (http.request.uri.path contains "/api/")
- Action: Challenge
- Rate: 30 requests per minute
```

---

## Part 5: Monitoring & Maintenance

### Monitor Linode Cron Job

**Check logs:**
```bash
# Real-time logs
docker compose -f docker-compose.cron.yml logs -f bigquery_cron

# Last 100 lines
docker compose -f docker-compose.cron.yml logs --tail=100 bigquery_cron
```

**Check container status:**
```bash
docker compose -f docker-compose.cron.yml ps
```

**Restart service if needed:**
```bash
docker compose -f docker-compose.cron.yml restart bigquery_cron
```

### Monitor Replit Autoscale

1. **Replit Dashboard** → Your deployment
2. View:
   - Active instances
   - Request rate
   - Compute unit usage
   - Error logs

### Set Up Alerts

**Linode:**
1. Dashboard → Your Linode → Settings
2. Enable **Email Alerts** for:
   - CPU usage > 80%
   - Disk usage > 80%
   - Network transfer quota

**Sentry (Application Errors):**
- Already configured in your Django app
- Monitors both Replit and Linode

---

## Part 6: Security Hardening

### Secure SSH Access

**Disable password authentication:**
```bash
sudo nano /etc/ssh/sshd_config
```

**Set these values:**
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

**Restart SSH:**
```bash
sudo systemctl restart sshd
```

### Keep System Updated

**Enable automatic security updates:**
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### Docker Security

**Run containers as non-root:**
Already configured in your Dockerfile with `USER django`

**Scan for vulnerabilities:**
```bash
# Install Trivy
sudo apt install -y wget apt-transport-https gnupg lsb-release
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
sudo apt update
sudo apt install -y trivy

# Scan image
trivy image stellarmapweb_bigquery_cron
```

---

## Part 7: Cost Breakdown

### Monthly Costs

| Service | Plan | Cost | Purpose |
|---------|------|------|---------|
| **Linode VPS** | Nanode 1GB | $5/month | BigQuery cron jobs |
| **Linode VPS** | Linode 2GB | $12/month | Recommended plan |
| **Replit Autoscale** | Pay-per-use | ~$5-15/month | Web app (scales to zero) |
| **Cloudflare** | Free Tier | $0/month | DDoS + CDN |
| **Astra DB** | Free Tier | $0/month | Database (up to 80GB) |
| **BigQuery** | Pay-per-query | $0-5/month | Lineage data (permanent storage model) |
| **Sentry** | Free Tier | $0/month | Error monitoring (5k events/month) |
| **TOTAL** | | **$10-32/month** | Complete production stack |

**Cost Optimization Tips:**
- Start with Linode Nanode 1GB ($5) for cron jobs
- Replit Autoscale scales to $0 when idle (perfect for low traffic)
- BigQuery costs decrease over time (permanent storage model)

---

## Part 8: Troubleshooting

### Issue: Cron job not running

**Check container:**
```bash
docker compose -f docker-compose.cron.yml ps
docker compose -f docker-compose.cron.yml logs bigquery_cron
```

**Verify environment:**
```bash
docker compose -f docker-compose.cron.yml exec bigquery_cron env | grep CASSANDRA
docker compose -f docker-compose.cron.yml exec bigquery_cron env | grep GOOGLE
```

### Issue: Can't connect to Astra DB

**Test connection:**
```bash
docker compose -f docker-compose.cron.yml exec bigquery_cron python manage.py shell

# In Python shell:
from cassandra.cqlengine import connection
connection.setup(['your-astra-id-region.apps.astra.datastax.com'], 'stellarmapweb')
print("✅ Connected!")
```

### Issue: Replit deployment failing

**Check deployment logs:**
1. Replit → Deployments → Your deployment
2. Click **Logs** tab
3. Look for errors

**Common issues:**
- Missing environment variables (check Secrets)
- Build errors (check Dockerfile)
- Port binding (must use `0.0.0.0:5000`)

### Issue: High costs

**Reduce Replit costs:**
- Increase idle timeout (scales to zero faster)
- Optimize database queries (fewer requests)
- Enable caching (reduce compute)

**Monitor usage:**
```bash
# Linode
df -h          # Disk usage
free -h        # Memory usage
top            # CPU usage
```

---

## Part 9: Upgrade Path

### Scale Linode VPS

**When to upgrade:**
- Cron job takes > 30 minutes
- CPU consistently > 80%
- Out of memory errors

**Resize Linode:**
1. Dashboard → Your Linode → Resize
2. Choose larger plan (2GB → 4GB → 8GB)
3. Reboot

### Add More Cron Workers

**Run multiple pipelines in parallel:**
```yaml
# docker-compose.cron.yml
services:
  bigquery_cron_1:
    # ... same config
    environment:
      - PIPELINE_WORKER_ID=1
  
  bigquery_cron_2:
    # ... same config
    environment:
      - PIPELINE_WORKER_ID=2
```

### Switch from Autoscale to Reserved VM

**When to switch:**
- Consistent high traffic (no idle time)
- Need websockets/stateful connections
- Want predictable costs

**Replit Reserved VM:**
- Dedicated resources
- Always-on
- Fixed monthly cost (~$15-25/month)

---

## ✅ Deployment Checklist

### Linode VPS
- [ ] Create Linode instance (Ubuntu 24.04)
- [ ] Set up firewall (UFW)
- [ ] Install Docker & Docker Compose
- [ ] Clone/upload StellarMapWeb code
- [ ] Create `.env` with all credentials
- [ ] Build and start cron service
- [ ] Verify cron job runs successfully
- [ ] Set up SSH key authentication
- [ ] Disable password authentication
- [ ] Enable automatic security updates

### Replit Autoscale
- [ ] Configure deployment (autoscale)
- [ ] Add all environment variables to Secrets
- [ ] Deploy to Replit Autoscale
- [ ] Test web application
- [ ] Verify autoscaling works

### Cloudflare
- [ ] Point domain to Replit
- [ ] Enable SSL (Full mode)
- [ ] Configure firewall rules
- [ ] Enable HTTPS enforcement

### Monitoring
- [ ] Set up Linode email alerts
- [ ] Configure Sentry error tracking
- [ ] Test deployment end-to-end
- [ ] Monitor costs for first week

---

## 🎉 Success!

Your hybrid architecture is now running:

1. **Replit Autoscale** serves the web app (scales automatically)
2. **Linode VPS** runs BigQuery cron jobs (always reliable)
3. **Cloudflare** protects against DDoS (free tier)
4. **Astra DB** stores all data (shared by both)

**Total cost: $10-32/month for a production-ready Stellar blockchain app!** 🚀

For support or questions, check:
- Linode Docs: https://www.linode.com/docs/
- Replit Docs: https://docs.replit.com/
- This project's issues: [GitHub Issues Link]
