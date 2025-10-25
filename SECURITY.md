# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within StellarMapWeb, please report it privately through one of the following channels:

1. **Preferred**: Create a private security advisory on GitHub (if repository has security advisories enabled)
2. **Alternative**: Contact the repository maintainers directly via their GitHub profile email or direct message

**Do not open public GitHub issues for security vulnerabilities.**

All security vulnerabilities will be promptly addressed. You can expect an initial response within 48 hours.

## Known Security Considerations

### Django Version (5.0.2)

**Current Status:** Django 5.0.2 is in use due to compatibility constraints.

**Known Vulnerabilities:** Django 5.0.2 has known security vulnerabilities that are fixed in versions 5.0.14+ and 5.1.x. However, upgrading breaks critical functionality in the current codebase.

**Mitigation:**
- The application is configured with `DEBUG=False` in production
- All security headers (HSTS, X-Frame-Options, CSP, etc.) are properly configured
- Input validation and CSRF protection are fully enabled
- Database credentials are stored in environment variables
- The application should only be deployed in trusted environments until Django can be safely upgraded

**Upgrade Path:** Planned for future release once compatibility issues are resolved.

### SQLParse

**Status:** Using latest version (0.5.3) with no known vulnerabilities.

## Security Best Practices

1. **Environment Variables:** Never commit `.env` files or expose secret keys
2. **HTTPS Only:** Always use HTTPS in production with proper SSL certificates
3. **Database Access:** Limit database access to application servers only
4. **Regular Updates:** Keep dependencies updated (check with `pip-audit`)
5. **Secrets Management:** Use environment variables or dedicated secrets managers

## Security Features

- **Input Validation:** Multi-layer validation for all user inputs
- **CSRF Protection:** Enabled on all forms
- **XSS Prevention:** Automatic template escaping
- **SQL Injection Prevention:** ORM-based queries only
- **Secure Headers:** HSTS, X-Frame-Options, CSP, etc.
- **Session Security:** Secure cookies, HTTP-only flags

## Triple-Pipeline Architecture Security

StellarMapWeb implements three data collection pipelines with comprehensive security controls:

### 1. SDK Pipeline Security (Stellar SDK)

**Rate Limiting:**
- Client-side rate limiter enforces 3500 requests/3600 seconds (97% of Horizon's 3600/hour limit)
- Sliding window algorithm with automatic cleanup of expired requests
- Thread-safe implementation using `asyncio.Lock`
- Simple sleep-based backpressure when limit reached (waits until window clears)

**Error Handling:**
- Tenacity retry decorator with exponential backoff on individual API calls (3 attempts max)
- Automatic Sentry error tracking for all exceptions
- Graceful degradation on API failures
- No sensitive data in error logs

**Input Validation:**
- Stellar account addresses validated through Django ORM constraints
- Network parameter validated against whitelist (`public`, `testnet`)
- No direct SQL queries - uses Django ORM exclusively

**Async Safety:**
- Thread-safe rate limiter with `asyncio.Lock` for concurrent request tracking
- Manual batching for concurrent processing (configurable via `--concurrent` parameter, default 5)
- Exception handling in `asyncio.gather()` with `return_exceptions=True`
- Proper async context manager cleanup (`__aenter__`/`__aexit__`)

**Secrets Management:**
- Environment variables via `EnvHelpers` for Horizon URLs
- No hardcoded API keys or endpoints
- Network-aware configuration (public vs testnet)

**Key Security Implementation:**
```python
# Rate limiting with thread safety - simple sleep-based backpressure
async with self._lock:
    # Clean expired requests
    while self.requests and self.requests[0] < now - self.time_window:
        self.requests.popleft()
    
    # Enforce limit by sleeping until window clears
    if len(self.requests) >= self.max_requests:
        wait_time = self.time_window - (now - self.requests[0])
        await asyncio.sleep(wait_time + 0.1)
```

### 2. API Pipeline Security (Horizon/Stellar Expert)

**Rate Limiting:**
- Horizon API: 180 requests/30 seconds (Horizon recommended limit)
- Stellar Expert: 5 requests/second
- Django cache-based rate limiting with atomic operations
- Per-IP and global rate limits

**Error Handling:**
- Tenacity retry with exponential backoff
- HTTP status code validation
- Timeout controls (30s default)
- Sentry integration for monitoring

**Input Validation:**
- Stellar address format validation (56-character G-prefixed addresses)
- Network parameter validation
- JSON response validation
- Content-Type header validation

**Secrets Management:**
- Environment variables for API endpoints
- No API keys required (public APIs)

### 3. BigQuery Pipeline Security (Google BigQuery)

**Cost Protection:**
- `BigQueryCostGuard` prevents runaway costs
- Configurable cost limits ($0.18-0.71/query)
- Admin panel cost warnings (yellow/red)
- Automatic fallback to free pipelines

**Authentication:**
- Google Cloud service account JSON credentials
- Environment variable-based credential storage (`GOOGLE_APPLICATION_CREDENTIALS_JSON`)
- No credentials in code or version control
- IAM-based access control

**Query Safety:**
- Parameterized queries only (no string concatenation)
- Query cost estimation before execution
- Row/byte limits enforced
- No dynamic SQL construction

**Error Handling:**
- Google Cloud exceptions caught and logged
- Sentry error tracking
- Graceful fallback to API pipeline on failures

**Key Security Implementation:**
```python
# Cost guard validation
if estimated_cost > self.max_cost:
    raise BigQueryCostGuardException(
        f"Query cost ${estimated_cost:.4f} exceeds limit ${self.max_cost:.4f}"
    )
```

### Pipeline-Wide Security Controls

**Database Security:**
- Django ORM only (no raw SQL)
- Composite primary keys with network isolation
- Environment-aware model loading (dev/prod)
- Automatic timestamp management

**Logging Security:**
- No sensitive data in logs (account addresses are public)
- Error messages truncated to 500 characters
- Sentry integration for production monitoring
- Structured logging with log levels

**Network Isolation:**
- Network parameter (`public`/`testnet`) enforced at pipeline level
- Separate database records per network
- No cross-network contamination

**Queue Synchronizer Security:**
- Atomic database operations
- Transaction safety for batch operations
- Network-aware synchronization
- No user input - internal operations only

### Security Testing

**Regression Testing:**
- 180+ tests across 45+ test files
- Security-focused tests for input validation
- Rate limiter tests for boundary conditions
- Mock-based testing for external API isolation

**Continuous Security:**
- `pip-audit` for dependency vulnerability scanning
- Sentry for runtime error monitoring
- LSP diagnostics for code quality
- Django security checks (`python manage.py check --deploy`)

### Security Recommendations

1. **Pipeline Selection:**
   - **SDK_ONLY** (Recommended): Free, fast, secure
   - **API_ONLY**: Free, reliable, well-tested
   - **BIGQUERY_WITH_API_FALLBACK**: Use only when necessary due to cost

2. **Environment Configuration:**
   - Set `DEBUG=False` in production
   - Configure `ALLOWED_HOSTS` properly
   - Use HTTPS for all API calls
   - Rotate Google Cloud service account keys regularly

3. **Monitoring:**
   - Monitor Sentry for pipeline errors
   - Review rate limiter statistics
   - Track BigQuery costs in Google Cloud Console
   - Set up alerts for unusual activity

4. **Access Control:**
   - Restrict admin panel access
   - Use strong admin passwords
   - Enable Django admin audit logging
   - Limit database access to application servers

## Running Security Audits

```bash
# Install pip-audit
pip install pip-audit

# Run security audit
pip-audit

# Check for outdated packages
pip list --outdated
```

## Production Deployment Checklist

- [ ] `DEBUG=False` in production settings
- [ ] Valid SSL/TLS certificate installed
- [ ] All security headers enabled
- [ ] Secrets stored in environment variables or secrets manager
- [ ] Database backups configured
- [ ] Error tracking (Sentry) configured
- [ ] Rate limiting enabled
- [ ] Admin URL changed from default `/admin/`
- [ ] Dependencies audited for vulnerabilities
- [ ] Firewall rules configured
- [ ] ALLOWED_HOSTS properly configured

## Contact

For security concerns:
- **Security Issues**: Follow the private reporting channels listed above
- **General Questions**: Open a public GitHub issue with the "question" label
- **Feature Requests**: Open a public GitHub issue with the "enhancement" label
