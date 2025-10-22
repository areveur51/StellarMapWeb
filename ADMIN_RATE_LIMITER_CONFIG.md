# API Rate Limiter Configuration System

## Overview
The API Rate Limiter Configuration system allows admins to control API request rates as percentages of maximum allowed rates, with automatic calculation of calls/minute and delay values.

## Admin Portal Access

### URL
`/admin/apiApp/apiratelimiterconfig/`

### Configuration Fields

#### 1. **Horizon API Percentage** (Default: 100%)
Controls the rate limit for Horizon API as a percentage of the safe maximum (120 req/min).

**Examples:**
- 100% = 120 req/min (0.50s delay)
- 85% = 102 req/min (0.59s delay)
- 50% = 60 req/min (1.00s delay)

#### 2. **Stellar Expert API Percentage** (Default: 83%)
Controls the rate limit for Stellar Expert API as a percentage of the conservative free tier maximum (50 req/min).

**Examples:**
- 100% = 50 req/min (1.20s delay)
- 85% = 42 req/min (1.43s delay)
- 50% = 25 req/min (2.40s delay)

### Maximum Rates Reference
- **Horizon API**: 120 requests/minute (based on 3600/hour safe limit)
- **Stellar Expert API**: 50 requests/minute (conservative free tier estimate)

## Features

### 1. Automatic Calculation
When you set a percentage, the system automatically calculates:
- **Calls per minute**: `percentage × maximum_rate`
- **Delay between calls**: `60 seconds ÷ calls_per_minute`

### 2. Live Dashboard Updates
The "API Health Monitoring" section on the dashboard displays real-time rate limits based on your percentage settings.

### 3. Color-Coded Display (Admin Portal)
- 🔴 **Red** (90-100%): High rate - aggressive API usage
- 🟡 **Yellow** (70-89%): Medium rate - balanced usage
- 🟢 **Green** (<70%): Low/safe rate - conservative usage

### 4. Singleton Configuration
Only one configuration can exist in the system. The admin portal automatically manages this as a singleton record with `config_id='default'`.

## Database Implementation

### Table: `api_rate_limiter_config`
Located in the **default SQLite database** (not Cassandra).

**Schema:**
```sql
CREATE TABLE api_rate_limiter_config (
    config_id VARCHAR(50) PRIMARY KEY,
    horizon_percentage INTEGER DEFAULT 100,
    stellar_expert_percentage INTEGER DEFAULT 83,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255) DEFAULT '',
    notes TEXT DEFAULT ''
);
```

### Database Routing
The `APIRateLimiterConfig` model is explicitly routed to the SQLite `default` database via `StellarMapWeb/router.py`:

```python
admin_config_models = ['BigQueryPipelineConfig', 'SchedulerConfig', 'APIRateLimiterConfig']
```

This ensures admin configuration models never interfere with Cassandra data.

## Usage in Code

### APIRateLimiter Integration
The `APIRateLimiter` class (`apiApp/helpers/api_rate_limiter.py`) reads configuration on initialization:

```python
from apiApp.helpers.api_rate_limiter import APIRateLimiter

limiter = APIRateLimiter(enable_logging=True)
limiter.wait_for_horizon()        # Uses configured Horizon delay
limiter.wait_for_stellar_expert() # Uses configured Stellar Expert delay
```

### Configuration Loader
```python
from apiApp.helpers.api_rate_limiter import get_rate_limiter_config

config = get_rate_limiter_config()
# Returns: {
#     'horizon_delay': 0.5,
#     'stellar_expert_delay': 1.2,
#     'horizon_burst_limit': 120,
#     'stellar_expert_burst_limit': 41
# }
```

### Fallback Behavior
If the configuration cannot be loaded (e.g., during initial setup), the system uses safe defaults:
- Horizon: 100% (120 req/min, 0.5s delay)
- Stellar Expert: 83% (41 req/min, 1.2s delay)

## Admin Portal Features

### Read-Only Fields
- `config_id`: Always set to "default"
- `created_at`: Timestamp of initial creation
- `updated_at`: Auto-updated on save
- `updated_by`: Auto-populated with current admin username

### Editable Fields
- `horizon_percentage`: 1-100 (integer)
- `stellar_expert_percentage`: 1-100 (integer)
- `notes`: Optional text notes for documentation

### Permissions
- **Add**: Only allowed if no configuration exists (singleton enforcement)
- **Delete**: Not allowed (prevents accidental deletion)
- **Change**: Allowed for authorized admins

## Dashboard Integration

The System Dashboard (`/dashboard/`) displays live API rate limit metrics in the "API Health Monitoring" section:

- **Horizon API (STELLAR)**: Shows current usage vs. configured limit
  - Example: "0/120 calls/min (0.5s delay)"
  
- **Stellar Expert API**: Shows current usage vs. configured limit
  - Example: "0/41 calls/min (1.2s delay)"

These values update automatically based on your admin portal settings.

## Example Workflow

### Scenario: Reduce API load during testing

1. Navigate to `/admin/apiApp/apiratelimiterconfig/`
2. Log in with admin credentials
3. Change `horizon_percentage` from 100% to 50%
4. Change `stellar_expert_percentage` from 83% to 50%
5. Click "Save"

**Result:**
- Horizon: 60 req/min (1.00s delay) instead of 120 req/min
- Stellar Expert: 25 req/min (2.40s delay) instead of 41 req/min
- Dashboard updates to show new limits
- API Pipeline automatically uses slower rates on next run

## Initial Setup

The default configuration is created automatically via SQL:

```sql
INSERT INTO api_rate_limiter_config (
    config_id,
    horizon_percentage,
    stellar_expert_percentage,
    updated_by,
    notes
) VALUES (
    'default',
    100,
    83,
    'system',
    'Initial configuration - 100% Horizon (120 req/min), 83% Stellar Expert (41 req/min)'
);
```

This runs once during initial system setup.

## Troubleshooting

### Issue: "SyntaxException: no viable alternative at character '_'"
**Cause**: Database router not properly routing the model to SQLite.

**Solution**: Verify `StellarMapWeb/router.py` includes `APIRateLimiterConfig` in the `admin_config_models` list and restart Django server.

### Issue: Configuration changes not taking effect
**Cause**: `APIRateLimiter` instances cache configuration on initialization.

**Solution**: The API Pipeline workflow creates a new `APIRateLimiter` instance on each run cycle (every 2 minutes), so changes take effect automatically within 2 minutes.

### Issue: Cannot access admin portal
**Cause**: No admin user created.

**Solution**: Create superuser with:
```bash
python manage.py createsuperuser
```

## Testing

### Manual Testing
1. Access admin portal: `/admin/apiApp/apiratelimiterconfig/`
2. Change percentage values
3. Verify dashboard shows updated limits
4. Check API Pipeline logs for new delay values

### Automated Testing
Tests should verify:
- Database routing to SQLite (not Cassandra)
- Singleton enforcement (only one config)
- Automatic calculation accuracy
- Fallback to defaults when config missing

## Security Considerations

1. **Admin-Only Access**: Configuration changes require Django admin authentication
2. **Audit Trail**: `updated_by` field tracks which admin made changes
3. **No Deletion**: Delete permission disabled to prevent accidental removal
4. **SQLite Isolation**: Configuration stored separately from Cassandra production data

## Performance Notes

- Configuration lookup is lightweight (single SQLite query)
- `APIRateLimiter` reads config once per initialization
- No real-time database polling during API calls
- Minimal overhead (<1ms per limiter instance creation)

## Future Enhancements

Possible improvements:
1. Per-endpoint rate limit customization
2. Time-based rate limit schedules (e.g., slower during peak hours)
3. Real-time configuration reload without workflow restart
4. Rate limit usage history and analytics
5. Alert notifications when approaching limits
