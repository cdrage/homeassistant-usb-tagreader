#!/bin/bash

# Startup script for NFC Reader with its own PCSCD daemon

# Function to log with timestamp
log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >&2
}

log_info "Starting PCSCD daemon..."

# Clean up any leftover pcscd socket from previous runs
rm -f /run/pcscd/pcscd.comm /run/pcscd/pcscd.pid

# Start pcscd in the background with auto-exit, foreground mode disabled, and polkit disabled
pcscd --auto-exit --foreground --disable-polkit &
PCSCD_PID=$!

# Wait a moment for pcscd to initialize
sleep 2

# Check if pcscd is running
if ! ps -p $PCSCD_PID > /dev/null 2>&1; then
    log_error "Failed to start PCSCD daemon"
    exit 1
fi

log_info "PCSCD daemon started successfully (PID: $PCSCD_PID)"

log_info "Starting NFC Reader application..."
cd /app 
python nfc_reader.py
ret=$?

if [ $ret -ne 0 ]; then
    log_error "NFC Reader application exited with error code $ret."
    log_info "Waiting for 65 seconds before exiting..."
    sleep 65
else
    log_info "NFC Reader application exited normally."
fi