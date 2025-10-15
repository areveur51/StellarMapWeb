#!/bin/bash

################################################################################
# StellarMapWeb Startup & Test Script
# 
# This script will:
# 1. Restart the Django application
# 2. Run comprehensive test suite
# 3. Display results and health status
#
# Usage: bash startup.sh
################################################################################

set -e          # Exit on error
set -o pipefail # Capture pipeline exit codes correctly

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════╗"
echo "║                                                        ║"
echo "║          StellarMapWeb Startup & Test Suite            ║"
echo "║                                                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"
}

# Function to print status
print_status() {
    echo -e "${CYAN}➜${NC} $1"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

################################################################################
# Step 1: Environment Check
################################################################################

print_header "1. Environment Check"

# Check Python version
print_status "Checking Python version..."
python --version
print_success "Python is available"

# Check Django installation
print_status "Checking Django installation..."
python -c "import django; print(f'Django version: {django.get_version()}')"
print_success "Django is installed"

# Check required environment variables
print_status "Checking environment variables..."
if [ -z "$DJANGO_SECRET_KEY" ]; then
    print_warning "DJANGO_SECRET_KEY not set (using default for development)"
else
    print_success "DJANGO_SECRET_KEY is configured"
fi

################################################################################
# Step 2: Database Check
################################################################################

print_header "2. Database Check"

print_status "Running database migrations..."

# Temporarily disable exit-on-error for migrations (they may fail in development mode)
set +e
MIGRATION_OUTPUT=$(python manage.py migrate --noinput 2>&1)
MIGRATION_EXIT_CODE=$?
set -e

if [ $MIGRATION_EXIT_CODE -eq 0 ]; then
    print_success "Database migrations completed"
    echo "$MIGRATION_OUTPUT" | grep -i "cassandra" >/dev/null && print_warning "Note: Cassandra models managed separately"
else
    print_warning "Migrations failed (this is normal with ENV=development due to Cassandra/SQLite conflicts)"
    print_status "SQLite tables will be created manually if needed"
fi

################################################################################
# Step 3: Environment Secrets & Workflow Restart Guidance
################################################################################

print_header "3. Environment Secrets & Workflow Status"

# Check current ENV value
CURRENT_ENV=$(printenv ENV || echo "not_set")
print_status "Current ENV setting: ${CURRENT_ENV}"

# Provide workflow restart guidance
echo ""
print_warning "IMPORTANT: If you changed the ENV secret, you MUST manually restart workflows!"
echo ""
echo -e "${YELLOW}Why?${NC} Workflows do not automatically pick up environment secret changes."
echo -e "${YELLOW}How to restart:${NC}"
echo "  1. Click the 'Django Server' workflow tab at the top of your workspace"
echo "  2. Click the square STOP button (⏹) to stop the workflow"
echo "  3. Click the Run button (▶) to restart the workflow"
echo ""
echo "After restarting the workflow, the new ENV value will take effect:"
echo "  • ENV=development  → Uses SQLite database"
echo "  • ENV=replit      → Uses Cassandra (Astra DB)"
echo "  • ENV=production  → Uses Cassandra (Astra DB)"
echo ""

# Detect workflow status
print_status "Checking workflow status..."
if pgrep -f "manage.py runserver" > /dev/null; then
    print_success "Django Server workflow is running"
    
    # Try to detect which database is actually being used by the running server
    WORKFLOW_PID=$(pgrep -f "manage.py runserver" | head -1)
    print_status "Django Server PID: ${WORKFLOW_PID}"
else
    print_warning "Django Server workflow is NOT running - please start it manually"
fi

print_status "Current workflows:"
echo "  - Django Server (port 5000)"
echo "  - BigQuery Pipeline"
echo ""

sleep 1
print_success "Environment check completed"

################################################################################
# Step 4: Run Test Suite
################################################################################

print_header "4. Running Test Suite"

# Create test results directory
mkdir -p test_results

# Run tests with detailed output
print_status "Running all Django tests..."
echo ""

# Temporarily disable exit-on-error to capture test results
set +e

# Run tests and capture output (use pattern to avoid test discovery issues)
python manage.py test --pattern="test_*.py" --verbosity=2 2>&1 | tee test_results/test_output.txt
TEST_EXIT_CODE=${PIPESTATUS[0]}  # Capture exit code from manage.py, not tee

# Re-enable exit-on-error
set -e

# Parse test results
TOTAL_TESTS=$(grep -oP "Ran \K\d+" test_results/test_output.txt 2>/dev/null || echo "0")
FAILED_TESTS=$(grep -oP "failures=\K\d+" test_results/test_output.txt 2>/dev/null || echo "0")
ERRORS=$(grep -oP "errors=\K\d+" test_results/test_output.txt 2>/dev/null || echo "0")

################################################################################
# Step 5: Test Results Summary
################################################################################

print_header "5. Test Results Summary"

echo -e "${CYAN}Test Statistics:${NC}"
echo "  Total Tests Run:     $TOTAL_TESTS"
echo "  Tests Passed:        $((TOTAL_TESTS - FAILED_TESTS - ERRORS))"
echo "  Tests Failed:        $FAILED_TESTS"
echo "  Errors:              $ERRORS"
echo ""

if [ $TEST_EXIT_CODE -eq 0 ]; then
    print_success "All tests passed! ✨"
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                        ║${NC}"
    echo -e "${GREEN}║          🎉 APPLICATION READY FOR USE! 🎉              ║${NC}"
    echo -e "${GREEN}║                                                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
else
    print_error "Some tests failed. Please review the output above."
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                                        ║${NC}"
    echo -e "${RED}║      ⚠️  TESTS FAILED - REVIEW REQUIRED  ⚠️            ║${NC}"
    echo -e "${RED}║                                                        ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
fi

################################################################################
# Step 6: Application Status
################################################################################

print_header "6. Application Status"

print_status "Application URLs:"
echo "  • Web Interface:    https://$(echo $REPL_SLUG).$(echo $REPL_OWNER).repl.co"
echo "  • Admin Portal:     https://$(echo $REPL_SLUG).$(echo $REPL_OWNER).repl.co/admin/"
echo "  • HVA Leaderboard:  https://$(echo $REPL_SLUG).$(echo $REPL_OWNER).repl.co/web/high-value-accounts/"
echo ""

print_status "Quick Navigation:"
echo "  • Search Accounts:  Use the search bar on any page"
echo "  • View Dashboard:   Click 'Dashboard' in sidebar"
echo "  • Check HVA:        Click 'High Value Accounts' in sidebar"
echo ""

################################################################################
# Step 7: Health Check
################################################################################

print_header "7. Health Check"

# Check if server is responding
print_status "Checking server health..."
sleep 3

if curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 | grep -q "200\|301\|302"; then
    print_success "Server is responding correctly"
else
    print_warning "Server may still be starting up..."
fi

################################################################################
# Final Summary
################################################################################

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Startup Complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""

print_status "Test results saved to: test_results/test_output.txt"
print_status "To view logs, use: tail -f /tmp/logs/*.log"
echo ""

exit $TEST_EXIT_CODE
