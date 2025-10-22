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

## Comprehensive Test Suite (Performance & Regression)

### New Test Categories with Pytest Markers

The project now uses pytest with structured markers for better test organization:

- **`@pytest.mark.unit`**: Fast unit tests with no external dependencies
- **`@pytest.mark.integration`**: Integration tests (database, API, external services)
- **`@pytest.mark.e2e`**: End-to-end workflow tests
- **`@pytest.mark.performance`**: Performance and optimization tests
- **`@pytest.mark.regression`**: Regression tests for bug fixes
- **`@pytest.mark.slow`**: Tests that take significant time

### New Comprehensive Test Files

#### 1. Performance - BigQuery Client Caching (`test_performance_bigquery_caching.py`)
Tests BigQuery client singleton caching optimization:
- Client caching with same credentials
- Cache invalidation on credential changes
- Credential hash calculation consistency
- Cost guard initialization per instance
- No client re-initialization in loops (performance regression test)

#### 2. Performance - API Endpoints (`test_performance_api_endpoints.py`)
Tests API endpoint optimizations:
- Pending accounts 30s cache TTL enforcement
- Cache invalidation after TTL expires
- No full table scans in lineage API (Cassandra optimization)
- In-memory hierarchy building from fetched records
- Rate limiting enforcement
- Response cache headers validation

#### 3. Query Builder Column Parity (`test_query_builder_column_parity.py`)
Tests ensuring UI matches database schema:
- Column definitions match Cassandra model fields
- All important model fields available in custom filter builder
- Parametrized tests for all tables (lineage, cache, hva, stages, hva_changes)
- Network column present in all tables
- Reasonable column counts per table
- Custom query API integration

#### 4. Vue.js Component Initialization (`test_vue_component_initialization.py`)
Tests Vue component initialization and rendering:
- Vue components initialize without JavaScript errors
- Polling intervals correctly configured (30s, not 15s)
- Page Visibility API handlers properly set up
- Event listener cleanup in beforeDestroy hook
- No raw Vue template syntax visible (regression test)
- Methods properly scoped within methods object
- No template rendering issues

#### 5. Database Integration (`test_database_integration.py`)
Tests dual database support (SQLite + Cassandra):
- SQLite fallback works correctly in development
- Cassandra models validate data correctly
- Model loader switches between databases based on environment
- Database routers work as expected
- N+1 query prevention
- Model timestamp auto-management
- HVA flag auto-set for balances >1M XLM

### Running Pytest Tests

#### Run Tests by Category
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests
pytest -m integration

# Performance tests
pytest -m "performance or regression"

# Exclude slow tests
pytest -m "not slow"
```

#### Run Tests in Parallel
```bash
# Use all CPU cores
pytest -n auto

# Use specific number of cores
pytest -n 4
```

#### Run with Coverage
```bash
pytest --cov=apiApp --cov=webApp --cov-report=html --cov-report=term-missing
```

#### Run Specific Test File
```bash
pytest apiApp/tests/test_performance_bigquery_caching.py -v
pytest apiApp/tests/test_query_builder_column_parity.py::TestQueryBuilderColumnParity -v
```

### CI/CD Integration

#### GitHub Actions Workflow

The `.github/workflows/test.yml` runs on every push and pull request with 5 parallel jobs:

1. **Unit Tests**: Fast tests with no external dependencies
2. **Integration Tests**: Database and API tests with test database
3. **Performance Tests**: Performance and regression tests
4. **Coverage**: Code coverage reporting with Codecov integration
5. **All Tests (Parallel)**: Full test suite using pytest-xdist

#### Local Pre-Push Testing
```bash
# Run the same tests as CI
pytest -m unit --tb=short --maxfail=5 -v
pytest -m integration --tb=short -v
pytest -m "performance or regression" --tb=short -v
```

### Test Configuration

Configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "StellarMapWeb.settings"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
testpaths = ["apiApp/tests", "webApp/tests"]
markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "integration: Integration tests (database, API, external services)",
    "e2e: End-to-end tests (full workflow tests)",
    "slow: Tests that take significant time",
    "performance: Performance and optimization tests",
    "regression: Regression tests for bug fixes"
]
```

### Best Practices for New Features

When adding new features:

1. **Write tests first** (TDD approach when possible)
2. **Add regression tests** for any bugs you fix
3. **Mark tests appropriately** with pytest markers
4. **Keep unit tests fast** (<100ms per test)
5. **Use mocking** for external dependencies
6. **Test one thing per test** (single responsibility)
7. **Run tests before committing** to catch issues early
8. **Verify CI passes** before merging

### Debugging Failed Tests

```bash
# View detailed output
pytest -vv --tb=long

# Stop on first failure
pytest -x

# Run only failed tests from last run
pytest --lf

# Enter debugger on failure
pytest --pdb
```

## Future Enhancements

### Test Coverage Goals
- [x] Add performance/load tests for cache system ✅
- [x] Add pytest with markers for better organization ✅
- [x] Add Query Builder schema parity tests ✅
- [x] Add Vue component initialization tests ✅
- [x] Add CI/CD with GitHub Actions ✅
- [ ] Add async helper method tests
- [ ] Add API response validation tests
- [ ] Add end-to-end workflow tests with Playwright
- [ ] Add database migration tests

### Testing Tools Implemented
- ✅ `pytest` for flexible test organization
- ✅ `pytest-django` for Django integration
- ✅ `pytest-xdist` for parallel test execution
- ✅ `pytest-cov` for coverage reports
- ✅ `pytest-mock` for enhanced mocking

### Testing Tools to Consider
- `factory_boy` for test data generation
- `freezegun` for time-dependent test cases
- `playwright` for E2E frontend testing

## Test Statistics

- **Total test files**: 45+ (41 existing + 5 new comprehensive tests)
- **Test categories**: 6 markers (unit, integration, e2e, performance, regression, slow)
- **CI jobs**: 5 parallel jobs in GitHub Actions
- **Coverage target**: >80% for critical code paths

## References

- Django Testing Documentation: https://docs.djangoproject.com/en/stable/topics/testing/
- Pytest Documentation: https://docs.pytest.org/
- Python unittest Mock: https://docs.python.org/3/library/unittest.mock.html
- Cassandra Best Practices: https://cassandra.apache.org/doc/latest/
- GitHub Actions: https://docs.github.com/en/actions
