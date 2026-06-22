#!/bin/bash
set -e
mkdir -p /data/uploads
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
