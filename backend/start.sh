#!/bin/bash

# Start the Agent Worker in the background
# Output logs to stdout
python main.py start &

# Start the Token Server in the foreground
# Railway requires the web service to listen on 0.0.0.0:$PORT
echo "Starting Token Server on port $PORT..."
python -m uvicorn token_server:app --host 0.0.0.0 --port $PORT
