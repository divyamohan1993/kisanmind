#!/bin/bash
# KisanMind — Entrypoint script
# Next.js on port 8080 (Cloud Run exposes this)
# Python backend on port 8081 (internal, proxied via Next.js rewrites)

echo "=== KisanMind Starting ==="

# Start the Python backend API on port 8081 (internal)
cd /app
PYTHONPATH=/app python -m uvicorn backend.main:app --host 0.0.0.0 --port 8081 &
BACKEND_PID=$!

# Wait a moment for backend to be ready
sleep 2

# Start the Next.js frontend on port 8080 (Cloud Run's exposed port)
cd /app/frontend
PORT=8080 npx next start -p 8080 &
FRONTEND_PID=$!

echo "Frontend running on :8080 (PID: $FRONTEND_PID) — Cloud Run exposed"
echo "Backend running on :8081 (PID: $BACKEND_PID) — internal, proxied via /api/*"

# Wait for either process to exit
wait -n $FRONTEND_PID $BACKEND_PID
EXIT_CODE=$?

# If one dies, kill the other
kill $FRONTEND_PID $BACKEND_PID 2>/dev/null
exit $EXIT_CODE
