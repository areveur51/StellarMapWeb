# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within StellarMapWeb, please send an email to [your-email]. All security vulnerabilities will be promptly addressed.

Please do not publicly disclose the issue until it has been addressed by the team.

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

For security concerns, please contact the maintainers directly rather than opening public issues.
