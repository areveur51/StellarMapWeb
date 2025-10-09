# Cloudflare DDoS Protection & Load Balancing Setup Guide

This guide walks you through setting up the complete **Free Tier Security Stack** for StellarMapWeb:

- ✅ Cloudflare Free (DDoS + SSL + CDN)
- ✅ Nginx (Load balancing + rate limiting)
- ✅ Docker setup with 2 Django instances
- ✅ Django-ratelimit (API rate limiting)

---

## 📋 Prerequisites

- Domain name (e.g., `stellarmapweb.com`)
- Server with Docker and Docker Compose installed
- Cloudflare account (free)

---

## Part 1: Cloudflare Setup (Free Tier)

### Step 1: Add Your Domain to Cloudflare

1. **Sign up/Login** to [Cloudflare](https://dash.cloudflare.com/)
2. **Add Site** → Enter your domain (e.g., `stellarmapweb.com`)
3. **Select Plan** → Choose **Free** ($0/month)
4. **Review DNS Records** → Cloudflare will scan and import your existing DNS records

### Step 2: Update Nameservers

Cloudflare will provide 2 nameservers (e.g., `nia.ns.cloudflare.com`, `sid.ns.cloudflare.com`)

**At your domain registrar** (GoDaddy, Namecheap, etc.):
1. Go to DNS settings
2. Replace existing nameservers with Cloudflare's nameservers
3. Wait for propagation (can take 1-24 hours)

### Step 3: Configure DNS Records

In Cloudflare → DNS → Records:

| Type | Name | Content | Proxy Status | TTL |
|------|------|---------|--------------|-----|
| A | @ | `YOUR_SERVER_IP` | ☁️ Proxied (Orange) | Auto |
| A | www | `YOUR_SERVER_IP` | ☁️ Proxied (Orange) | Auto |
| CNAME | api | `yourdomain.com` | ☁️ Proxied (Orange) | Auto |

**Important:** Ensure **Proxy status is "Proxied" (orange cloud)** for DDoS protection!

### Step 4: Enable SSL/TLS

**SSL/TLS → Overview:**
- **Encryption mode:** Full (⚠️ NOT "Full (strict)" - our Nginx serves HTTP internally)
- **Always Use HTTPS:** ON
- **Automatic HTTPS Rewrites:** ON
- **Minimum TLS Version:** TLS 1.2

**Note:** We use "Full" mode because Nginx serves HTTP (port 80) internally to Django. Cloudflare handles HTTPS to users, then connects to Nginx via HTTP. This is secure because traffic between Cloudflare and your server is on Cloudflare's private network.

**Edge Certificates:**
- **Always Use HTTPS:** ON
- **HTTP Strict Transport Security (HSTS):** Enable (after testing)
  - Max Age: 12 months
  - Include subdomains: Yes
  - Preload: Yes

### Step 5: Security Settings

**Security → Settings:**
- **Security Level:** Medium (or High during attacks)
- **Challenge Passage:** 30 minutes
- **Browser Integrity Check:** ON

**Firewall Rules (Free - 5 rules max):**

1. **Block bad bots:**
   ```
   Field: Threat Score
   Operator: Greater than
   Value: 10
   Action: Block
   ```

2. **Rate limit API (if you upgrade to Pro):**
   ```
   Field: URI Path
   Operator: contains
   Value: /api/
   Rate: 100 requests per minute
   Action: Challenge
   ```

**Under Attack Mode (Emergency):**
- Security → Settings → "I'm Under Attack Mode"
- Presents JavaScript challenge to all visitors
- Enable only during active DDoS attacks

### Step 6: Speed & Caching

**Speed → Optimization:**
- **Auto Minify:** Check CSS, JavaScript, HTML
- **Brotli:** ON
- **Rocket Loader:** OFF (can break Django templates)

**Caching → Configuration:**
- **Caching Level:** Standard
- **Browser Cache TTL:** 4 hours

**Page Rules (Free - 3 rules max):**

1. **Cache static assets:**
   ```
   URL: *stellarmapweb.com/static/*
   Settings: 
     - Cache Level: Cache Everything
     - Edge Cache TTL: 1 month
   ```

2. **Bypass cache for API:**
   ```
   URL: *stellarmapweb.com/api/*
   Settings: 
     - Cache Level: Bypass
   ```

3. **Always HTTPS:**
   ```
   URL: *stellarmapweb.com/*
   Settings: 
     - Always Use HTTPS: ON
   ```

---

## Part 2: Server Setup with Nginx Load Balancer

### Step 1: Collect Static Files

```bash
# Collect Django static files
python manage.py collectstatic --noreply
```

### Step 2: Update Environment Variables

Create/update `.env` file:

```bash
# Production settings
DJANGO_SETTINGS_MODULE=StellarMapWeb.production
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,api.yourdomain.com
SECURE_SSL_REDIRECT=True

# Admin URL (change for security)
ADMIN_URL=secure-admin-panel/

# Add all your other secrets
DJANGO_SECRET_KEY=your-secret-key
ASTRA_DB_TOKEN=your-token
# ... etc
```

### Step 3: Start Services with Docker Compose

**Choose Your Setup:**

**Option A: Production with Redis (Recommended for Load Balancing)**
```bash
# Build and start all services with Redis for cluster-wide rate limiting
docker-compose -f docker-compose.redis.yml up -d --build

# Verify all containers are running (including redis)
docker-compose -f docker-compose.redis.yml ps

# Check logs
docker-compose -f docker-compose.redis.yml logs -f
```

**Option B: Single Instance (No Redis)**
```bash
# Build and start services without Redis (single instance only)
docker-compose -f docker-compose.nginx.yml up -d --build

# Note: Rate limiting will NOT work correctly across django1 and django2
# Use this only for testing or single-instance deployments

# Verify containers
docker-compose -f docker-compose.nginx.yml ps
```

**⚠️ Important:** For production with load balancing, use Option A (docker-compose.redis.yml) to ensure rate limiting works correctly across all Django instances.

### Step 4: Test Health Check

```bash
# Test from server
curl http://localhost/health/

# Test from internet (should return JSON)
curl https://yourdomain.com/health/
```

Expected response:
```json
{
  "status": "healthy",
  "service": "stellarmapweb",
  "version": "1.0"
}
```

### Step 5: Test Load Balancing

```bash
# Make multiple requests - should distribute across django1 and django2
for i in {1..10}; do
  curl -s https://yourdomain.com/health/ | jq
  echo "---"
done

# Check which container handled each request
docker-compose -f docker-compose.nginx.yml logs django1 | grep health
docker-compose -f docker-compose.nginx.yml logs django2 | grep health
```

---

## Part 3: Test Rate Limiting

### Test Nginx Rate Limiting

```bash
# Send rapid requests to search endpoint (limit: 2/s)
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code}\n" https://yourdomain.com/search/
done

# Expected: First few return 200, then 429 (Too Many Requests)
```

### Test Django Rate Limiting

```bash
# Send rapid requests to search view (limit: 20/min per IP)
for i in {1..25}; do
  curl -s -o /dev/null -w "%{http_code}\n" https://yourdomain.com/search/?account=GABC...
done

# Expected: First 20 return 200, then 429
```

---

## Part 4: Monitoring & Maintenance

### Monitor Traffic (Cloudflare Dashboard)

**Analytics → Traffic:**
- Total requests
- Bandwidth saved by caching
- Threats blocked
- Geographic distribution

**Security → Events:**
- View blocked requests
- Challenge solves
- Rate limiting events

### Monitor Server Health

```bash
# Check all services status
docker-compose -f docker-compose.nginx.yml ps

# View real-time logs
docker-compose -f docker-compose.nginx.yml logs -f

# Check Nginx access logs
docker exec stellarmapweb_nginx tail -f /var/log/nginx/access.log

# Check Nginx error logs
docker exec stellarmapweb_nginx tail -f /var/log/nginx/error.log

# Monitor Django application logs
docker-compose -f docker-compose.nginx.yml logs -f django1 django2
```

### Health Check Endpoints

- **Server health:** `https://yourdomain.com/health/`
- **API health:** `https://yourdomain.com/api/`

### Restart Services

```bash
# Restart all services
docker-compose -f docker-compose.nginx.yml restart

# Restart only Nginx
docker-compose -f docker-compose.nginx.yml restart nginx

# Restart Django instances
docker-compose -f docker-compose.nginx.yml restart django1 django2

# View updated logs
docker-compose -f docker-compose.nginx.yml logs -f
```

---

## Part 5: Security Hardening Checklist

### ✅ Cloudflare

- [x] SSL/TLS set to "Full" (NOT "Full (strict)" - we use HTTP to origin)
- [x] Always Use HTTPS enabled
- [x] HSTS enabled
- [x] Proxy status "Proxied" (orange cloud) for all records
- [x] Firewall rules configured
- [x] Page rules for caching configured
- [x] Security level set to Medium or High

### ✅ Django

- [x] `DEBUG=False` in production
- [x] `ALLOWED_HOSTS` properly configured
- [x] `SECURE_SSL_REDIRECT=True`
- [x] Session cookies secure
- [x] CSRF protection enabled
- [x] Rate limiting on sensitive endpoints
- [x] Admin URL changed from default

### ✅ Nginx

- [x] Rate limiting configured
- [x] Connection limits per IP
- [x] Security headers added
- [x] Static files served by Nginx
- [x] Gzip compression enabled
- [x] Health checks configured

### ✅ Docker

- [x] Containers running as non-root users
- [x] Health checks configured
- [x] Restart policy set to `unless-stopped`
- [x] Logs properly configured
- [x] Volumes for persistent data

---

## Part 6: Troubleshooting

### Issue: Site not loading

**Check:**
1. DNS propagation: `nslookup yourdomain.com`
2. Cloudflare status: Dashboard → Overview
3. Server status: `docker-compose -f docker-compose.nginx.yml ps`
4. Nginx logs: `docker-compose -f docker-compose.nginx.yml logs nginx`

### Issue: Rate limiting too aggressive

**Adjust Nginx limits** in `nginx.conf`:
```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;  # Increase from 10r/s
```

**Adjust Django limits** in `webApp/views.py`:
```python
@ratelimit(key='ip', rate='30/m', method='GET', block=True)  # Increase from 20/m
```

### Issue: Health check failing

**Test directly:**
```bash
# Test Django directly (bypass Nginx)
docker exec stellarmapweb_django1 curl http://localhost:5000/health/

# Test Nginx
curl http://localhost/health/
```

### Issue: SSL errors

**Verify SSL settings:**
1. Cloudflare → SSL/TLS → Overview → **Full** (NOT "Full (strict)")
2. Check `.env`: `SECURE_SSL_REDIRECT=True`
3. Check Nginx is accepting connections: `docker logs stellarmapweb_nginx`

### Issue: Rate limiting not working across instances

**⚠️ Important:** The default setup uses `LocMemCache` which is NOT shared across Django instances. This means rate limits are tracked separately on `django1` and `django2`.

**Solution: Add Redis for cluster-wide rate limiting**

1. **Add Redis to `docker-compose.nginx.yml`:**
```yaml
redis:
  image: redis:alpine
  container_name: stellarmapweb_redis
  restart: unless-stopped
  networks:
    - stellarmapweb_network
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 30s
    timeout: 10s
    retries: 3
```

2. **Update `StellarMapWeb/production.py`:**
```python
# Replace LocMemCache with Redis
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
    }
}
```

3. **Install Redis client:**
```bash
pip install redis
# or
poetry add redis
```

4. **Restart services:**
```bash
docker-compose -f docker-compose.nginx.yml up -d
```

Now rate limits are enforced cluster-wide! 🎉

---

## Part 7: Scaling Beyond Free Tier

### When to Upgrade

**Cloudflare Pro ($20/month):**
- Advanced DDoS protection
- Web Application Firewall (WAF)
- Image optimization
- More page rules (20 vs 3)

**Cloudflare Load Balancing ($5/origin/month):**
- Geo-routing
- Health checks with notifications
- Automatic failover
- Traffic steering

### Add More Django Instances

Edit `docker-compose.nginx.yml`:

```yaml
django3:
  build: .
  command: gunicorn --bind 0.0.0.0:5000 --workers 4 StellarMapWeb.wsgi:application
  # ... same config as django1/django2
```

Update `nginx.conf`:
```nginx
upstream django_backend {
    least_conn;
    server django1:5000 max_fails=3 fail_timeout=30s;
    server django2:5000 max_fails=3 fail_timeout=30s;
    server django3:5000 max_fails=3 fail_timeout=30s;  # Add new instance
}
```

Restart services:
```bash
docker-compose -f docker-compose.nginx.yml up -d --scale django1=1 --scale django2=1 --scale django3=1
```

---

## 🎯 Quick Reference

### Common Commands

```bash
# Start services
docker-compose -f docker-compose.nginx.yml up -d

# Stop services
docker-compose -f docker-compose.nginx.yml down

# View logs
docker-compose -f docker-compose.nginx.yml logs -f

# Restart services
docker-compose -f docker-compose.nginx.yml restart

# Rebuild and restart
docker-compose -f docker-compose.nginx.yml up -d --build

# Check health
curl https://yourdomain.com/health/
```

### Important URLs

- **Cloudflare Dashboard:** https://dash.cloudflare.com/
- **Health Check:** https://yourdomain.com/health/
- **Admin Panel:** https://yourdomain.com/[ADMIN_URL]/

---

## 📊 Expected Performance

With this setup, you should see:

- ✅ **99.9% uptime** (with health checks and auto-restart)
- ✅ **DDoS protection** (Cloudflare blocks attacks before they reach your server)
- ✅ **50-70% bandwidth savings** (Cloudflare CDN caching)
- ✅ **2x capacity** (load balanced across 2 Django instances)
- ✅ **Rate limiting** prevents abuse (Nginx + Django layers)
- ✅ **SSL/TLS encryption** for all traffic
- ✅ **Auto-failover** if one Django instance fails

---

## 🚀 You're All Set!

Your StellarMapWeb application is now protected with:
- Enterprise-grade DDoS protection (Cloudflare)
- Load balancing (Nginx)
- Rate limiting (Nginx + Django)
- SSL/TLS encryption
- Auto-scaling and failover

All for **$0/month** on the free tier! 🎉

For questions or issues, check the Troubleshooting section or review the logs.
