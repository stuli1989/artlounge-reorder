#!/usr/bin/env bash
# Idempotent environment setup for mission workers
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Checking backend dependencies..."
cd src
./venv/Scripts/python -m pip install -r requirements.txt -q 2>/dev/null || true
cd ..

echo "Checking frontend dependencies..."
cd src/dashboard
npm install --silent 2>/dev/null || true
cd ../..

echo "Init complete."
