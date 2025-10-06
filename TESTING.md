# StellarMapWeb Testing Guide

## Overview

This document describes the comprehensive test suite for StellarMapWeb, designed to quickly identify errors in Cassandra database integration, helper functions, cron workflows, and view logic.

## Test Types

### Unit Tests (Mocked Dependencies)
Fast, isolated tests that mock external dependencies like Cassandra operations and API calls. These tests validate business logic, data transformations, and workflow state transitions WITHOUT hitting the actual database.

**Advantages:**
- Fast execution (milliseconds)
- No database setup required
- Reliable and repeatable
- Good for CI/CD pipelines

**Limitations:**
- Don't catch schema drift
- Don't catch Cassandra query errors
- Don't validate actual database operations

### Integration Tests (Real Cassandra)
Tests that exercise actual Cassandra models and database operations. These tests catch schema mismatches, composite primary key issues, and real query errors.

**Advantages:**
- Catches schema drift and migration issues
- Validates composite primary keys work correctly
- Tests real Cassandra QuerySet operations
- Ensures timestamp auto-management functions

**Limitations:**
- Slower execution (seconds)
- Requires database connection
- May have cleanup issues
- Not ideal for CI/CD without dedicated test database

## Test Structure

### 1. Cassandra Model Unit Tests (Mocked)
**File**: `apiApp/tests/test_cassandra_models.py`  
**Type**: Unit tests with mocked `.objects` managers

Tests model structure and field validation without hitting Cassandra:
- `StellarAccountSearchCache`: Composite primary key (stellar_account, network)
- `StellarCreatorAccountLineage`: Composite primary key (stellar_account, network_name)
- `ManagementCronHealth`: Composite primary key (cron_name, created_at DESC)

**What These Tests Catch**:
- Model field definitions are correct
- Timestamp logic is present
- No UUID `id` field present (avoiding BaseModel conflicts)

**What These Tests DON'T Catch**:
- Schema drift between models and actual Cassandra tables
- Real query execution errors
- Composite primary key query efficiency

### 1b. Cassandra Real Integration Tests
**File**: `apiApp/tests/test_cassandra_integration.py`  
**Type**: Integration tests with REAL Cassandra operations

Tests actual database operations against live Cassandra:
- Create, save, and retrieve records with composite keys
- Update operations and timestamp management
- Filter queries by account and network
- Clustering order retrieval (DESC for health checks)
- JSON storage and parsing in cached_json field

**What These Tests Catch**:
- Schema mismatches between models and tables
- Composite primary key query errors
- Real Cassandra QuerySet filter issues
- Timestamp auto-management actually works
- Data serialization/deserialization bugs

**Note**: These tests require active Cassandra connection and may need cleanup.

### 2. Cache Helper Unit Tests (Mocked)
**File**: `apiApp/tests/test_sm_cache_helpers.py`  
**Type**: Unit tests with mocked Cassandra operations

Tests `StellarMapCacheHelpers` business logic with mocked `.objects`:
- Cache freshness checks (< 12 hours)
- PENDING entry creation for new/existing accounts
- Cache updates with tree_data
- JSON parsing and retrieval
- Boundary conditions (exactly 12 hours, missing data)

**What These Tests Catch**:
- 12-hour freshness calculation logic
- PENDING entry creation workflow
- JSON serialization/parsing logic
- Edge case handling (null data, missing fields)

**What These Tests DON'T Catch**:
- Real database save operations
- Actual Cassandra filter query issues
- Transaction or concurrency problems

### 3. Lineage Helper Tests
**File**: `apiApp/tests/test_sm_creatoraccountlineage_helpers.py`

Tests `StellarMapCreatorAccountLineageHelpers` with mocked Cassandra:
- Lineage record creation
- Fetching lineage by account and network
- Updating from Horizon API data
- Extracting creator accounts from operations
- Grandparent lineage traversal
- Status tracking through workflow

### 4. Cron Command Tests
**File**: `apiApp/tests/test_cron_commands.py`

Tests Django management cron commands with mocked APIs and DB:
- `cron_make_parent_account_lineage`: PENDING entry processing
- `cron_collect_account_horizon_data`: Horizon API integration
- `cron_health_check`: Health monitoring record creation
- Status updates on completion
- Error handling for API failures
- Multiple entry processing

### 5. View Integration Tests
**File**: `apiApp/tests/test_views_integration.py`

Tests `search_view` with mocked Cassandra:
- Fresh cache hit returns cached data
- Stale cache creates PENDING entry
- Missing cache creates PENDING entry
- Lineage data fetching
- Stellar address validation
- Context preparation for templates
- Network parameter handling
- Immediate refresh attempts

## Running Tests

### Run All Tests
```bash
python run_tests.py
```

### Run with Verbose Output
```bash
python run_tests.py --verbose
```

### Run Tests for Specific App
```bash
python run_tests.py --app apiApp
```

### Run Tests Matching Pattern
```bash
python run_tests.py --pattern test_cassandra_*
```

### Using Django's Test Command
```bash
python manage.py test apiApp.tests
python manage.py test apiApp.tests.test_cassandra_models
python manage.py test apiApp.tests.test_sm_cache_helpers.StellarMapCacheHelpersTest.test_check_cache_freshness_fresh_data
```

## What Tests Catch

### Database Integration Issues
- **Composite Primary Key Failures**: Tests verify all models use correct composite keys
- **UUID Conflicts**: Tests ensure no BaseModel `id` field interference
- **Timestamp Issues**: Tests validate auto-management of created_at/updated_at
- **Query Efficiency**: Tests confirm no ALLOW FILTERING required

### Cache System Issues
- **Freshness Logic Errors**: Tests verify 12-hour boundary calculations
- **PENDING Entry Creation**: Tests ensure proper workflow triggering
- **JSON Parsing Failures**: Tests handle malformed cached data
- **Missing Data Handling**: Tests verify graceful null/missing data handling

### Lineage Workflow Issues
- **Creator Extraction Failures**: Tests verify operations data parsing
- **Grandparent Traversal Errors**: Tests ensure recursive lineage building
- **Status Transition Problems**: Tests validate workflow progression
- **API Integration Failures**: Tests mock Horizon API responses

### Cron Job Issues
- **PENDING Entry Processing**: Tests verify cron finds entries to process
- **API Call Failures**: Tests handle 404/500 responses
- **Health Check Failures**: Tests detect stale/unhealthy jobs
- **Cache Update Failures**: Tests ensure tree_data stored after completion

### View Logic Issues
- **Cache Flow Errors**: Tests verify fresh/stale/missing cache paths
- **PENDING Creation Failures**: Tests ensure entries created when needed
- **Context Building Errors**: Tests validate template context
- **Network Parameter Issues**: Tests verify public/testnet handling

## Test Philosophy

### Mocking Strategy
Tests use extensive mocking to:
- **Avoid Live Database**: No actual Cassandra writes during tests
- **Isolate Components**: Test each component independently
- **Fast Execution**: Tests run in seconds, not minutes
- **Repeatable Results**: No dependency on external services

### What We Mock
- `StellarAccountSearchCache.objects`: All Cassandra ORM operations
- `StellarCreatorAccountLineage.objects`: All lineage database operations
- `ManagementCronHealth.objects`: All health check database operations
- `requests.get`: All Horizon API calls
- Helper class instances: All helper method calls in views

### What We Don't Mock
- Business logic within helper methods
- Data transformations and calculations
- Workflow status progression logic
- Timestamp calculation logic

## Continuous Integration

### Pre-Deployment Checklist
Before deploying code changes:
1. Run full test suite: `python run_tests.py --verbose`
2. Verify all tests pass
3. Check for new deprecation warnings
4. Review test coverage for new code

### When to Add New Tests
- **New Models**: Add full CRUD test suite
- **New Helper Methods**: Add unit tests with mocking
- **New Cron Jobs**: Add workflow progression tests
- **New Views**: Add context and rendering tests
- **Bug Fixes**: Add regression test for the bug

## Troubleshooting

### ImportError for Models
If tests fail with import errors:
```bash
export DJANGO_SETTINGS_MODULE=StellarMapWeb.settings
python manage.py test
```

### Mock Not Working
Ensure patch paths match import paths in tested file:
```python
# If views.py has: from apiApp.helpers.sm_cache import StellarMapCacheHelpers
# Then patch must use: @patch('webApp.views.StellarMapCacheHelpers')
```

### Cassandra Connection Errors
Tests should NOT connect to real Cassandra. If seeing connection errors:
- Verify all `objects` are mocked
- Check patch decorators are applied
- Ensure mocks return expected types

## Future Enhancements

### Test Coverage Goals
- [ ] Add async helper method tests
- [ ] Add API response validation tests
- [ ] Add performance/load tests for cache system
- [ ] Add end-to-end workflow tests
- [ ] Add database migration tests

### Testing Tools to Consider
- `pytest` for more flexible test organization
- `coverage.py` for test coverage reports
- `factory_boy` for test data generation
- `freezegun` for time-dependent test cases

## References

- Django Testing Documentation: https://docs.djangoproject.com/en/stable/topics/testing/
- Python unittest Mock: https://docs.python.org/3/library/unittest.mock.html
- Cassandra Best Practices: https://cassandra.apache.org/doc/latest/
