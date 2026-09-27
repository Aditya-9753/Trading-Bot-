#!/usr/bin/env bash
set -euo pipefail

echo "============================================="
echo "  TradeBot Production Deployment Script"
echo "============================================="

# Ensure .env exists
if [ ! -f .env ]; then
  echo "Error: .env file not found. Copy .env.example to .env and configure it first."
  exit 1
fi

echo "1. Pulling latest code and containers..."
docker compose pull || true

echo "2. Building and starting services..."
docker compose up -d --build --remove-orphans

echo "3. Waiting for services to become healthy..."
sleep 5

for i in {1..30}; do
  if docker compose ps | grep -q "(healthy)"; then
    echo "Services are running and healthy!"
    break
  fi
  echo "Waiting for healthchecks... ($i/30)"
  sleep 3
done

echo "4. Pruning unused old Docker images..."
docker image prune -f

echo "============================================="
echo "  TradeBot Deployment Completed Successfully!"
echo "============================================="
