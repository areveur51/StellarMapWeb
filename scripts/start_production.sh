#!/bin/bash
# Production startup script
# Runs both the web server (Gunicorn) and the background scheduler

echo "========================================="
echo "Starting StellarMapWeb Production"
echo "========================================="

# Start the background scheduler in the background
echo "Starting background scheduler..."
python scripts/run_scheduler.py &
SCHEDULER_PID=$!
echo "Scheduler started with PID: $SCHEDULER_PID"

# Give the scheduler a moment to initialize
sleep 2

# Start Gunicorn web server (foreground)
echo "Starting Gunicorn web server on port 3000..."
exec gunicorn --bind 0.0.0.0:3000 --workers 4 --timeout 120 StellarMapWeb.wsgi:application
