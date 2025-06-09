#!/bin/bash

# Startup script for NFC Reader with PCSCD
echo "Starting PCSCD daemon..."

# Start PCSCD in background
pcscd --auto-exit &

# Wait a moment for PCSCD to initialize
sleep 2

# Check if PCSCD is running
if ! pgrep -x "pcscd" > /dev/null; then
    echo "ERROR: Failed to start PCSCD daemon"
    exit 1
fi

echo "PCSCD started successfully"

# Send SIGTERM to stop PCSCD gracefully on exit
trap "pkill -SIGTERM pcscd" EXIT

# Switch to non-root user and run the Python application
echo "Starting NFC Reader application..."
exec su -c "cd /app && python nfc_reader.py" nfcuser

# Wait a while to avoid docker restarting the container immediately
echo "NFC Reader application exited, probably due to an error."
echo "Waiting for 65 seconds before exiting..."
sleep 65