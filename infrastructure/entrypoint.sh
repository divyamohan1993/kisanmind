#!/bin/bash
# KisanMind — Entrypoint script
# Runs both the Python backend API and Next.js frontend

echo "=== KisanMind Starting ==="

# Start the Next.js frontend on port 3000
cd /app/frontend
npx next start -p 3000 &
FRONTEND_PID=$!

# Start the Python backend API on port 8080
cd /app
python -m agents.brain.orchestrator &
BACKEND_PID=$!

echo "Frontend running on :3000 (PID: $FRONTEND_PID)"
echo "Backend running on :8080 (PID: $BACKEND_PID)"

# Wait for either process to exit
wait -n $FRONTEND_PID $BACKEND_PID
EXIT_CODE=$?

# If one dies, kill the other
kill $FRONTEND_PID $BACKEND_PID 2>/dev/null
exit $EXIT_CODE
