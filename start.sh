#!/bin/bash
set -e

# Start Xvfb virtual display on display :99
echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for Xvfb to be ready
sleep 2

# Verify Xvfb is running
if ! ps -p $XVFB_PID > /dev/null; then
    echo "ERROR: Xvfb failed to start"
    exit 1
fi

# Set DISPLAY environment variable
export DISPLAY=:99
echo "Xvfb started on display :99"

# Start window manager
echo "Starting Fluxbox window manager..."
fluxbox &

# Start VNC server (allows viewing the display)
echo "Starting VNC server on port 5900..."
x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -forever -shared -bg
echo "VNC server started. Connect on port 5900"

# Function to cleanup on exit
cleanup() {
    echo "Shutting down Xvfb..."
    kill $XVFB_PID 2>/dev/null || true
    wait $XVFB_PID 2>/dev/null || true
}

# Trap signals to cleanup
trap cleanup SIGTERM SIGINT

# Start Streamlit (this will run in foreground)
echo "Starting Streamlit..."
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true