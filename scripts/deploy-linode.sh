#!/bin/bash

# Linode VPS Deployment Script for StellarMapWeb Cron Jobs
# This script automates the deployment of BigQuery cron service to Linode VPS

set -e  # Exit on error

echo "🚀 StellarMapWeb - Linode Deployment Script"
echo "==========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please create .env file with all required credentials"
    echo "See .env.example for reference"
    exit 1
fi

# Verify required environment variables
echo "🔍 Checking environment variables..."
required_vars=(
    "DJANGO_SECRET_KEY"
    "CASSANDRA_DB_NAME"
    "ASTRA_DB_ID"
    "ASTRA_DB_TOKEN"
    "GOOGLE_APPLICATION_CREDENTIALS_JSON"
)

for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env; then
        echo -e "${RED}❌ Missing required variable: ${var}${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ All required variables found${NC}"
echo ""

# Build Docker image
echo "🏗️  Building Docker image..."
docker compose -f docker-compose.cron.yml build

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Build successful${NC}"
else
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi
echo ""

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker compose -f docker-compose.cron.yml down

# Start services
echo "▶️  Starting BigQuery cron service..."
docker compose -f docker-compose.cron.yml up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Service started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start service${NC}"
    exit 1
fi
echo ""

# Wait for container to be healthy
echo "⏳ Waiting for container to be ready..."
sleep 5

# Check container status
echo "📊 Container status:"
docker compose -f docker-compose.cron.yml ps
echo ""

# Show logs
echo "📋 Recent logs:"
docker compose -f docker-compose.cron.yml logs --tail=20 bigquery_cron
echo ""

# Summary
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:    docker compose -f docker-compose.cron.yml logs -f bigquery_cron"
echo "  Restart:      docker compose -f docker-compose.cron.yml restart bigquery_cron"
echo "  Stop:         docker compose -f docker-compose.cron.yml down"
echo "  Shell access: docker compose -f docker-compose.cron.yml exec bigquery_cron bash"
echo ""
echo "🎉 BigQuery cron job is now running on Linode VPS!"
