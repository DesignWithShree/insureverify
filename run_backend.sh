#!/usr/bin/env bash
# Starts the FastAPI backend on http://localhost:8000
cd "$(dirname "${BASH_SOURCE[0]}")/backend"
source venv/bin/activate
uvicorn main:app --reload --port 8000
