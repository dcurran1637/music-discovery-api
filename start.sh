#!/bin/bash
# Startup script for Render deployment
# Ensures correct host and port binding

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
