#!/bin/bash

# Start Token Server
# Cleanup previous runs
pkill -f "python token_server.py" || true
pkill -f "python main.py dev" || true
# Be careful with npm/node so we don't kill other things, but lsof is safer?
# Or just accept duplicates on frontend (vite handles ports).
# For backend, we MUST kill port 8000 user.
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

echo "Starting Token Server..."
cd backend
source venv/bin/activate
uvicorn token_server:app --port 8000 &
PID_TOKEN=$!

# Start Agent (Dev mode)
echo "Starting Agent..."
python main.py dev &
PID_AGENT=$!

# Start Frontend
echo "Starting Frontend..."
cd ../frontend
npm run dev &
PID_FRONTEND=$!

# Wait for all
wait $PID_TOKEN $PID_AGENT $PID_FRONTEND
