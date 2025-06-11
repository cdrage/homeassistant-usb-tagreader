#!/bin/bash

# Startup script for NFC Reader connecting to host PCSCD

# Function to log with timestamp
log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >&2
}

log_info "Connecting to host PCSCD daemon..."

# Check if we can connect to PCSCD socket
if [ ! -S /run/pcscd/pcscd.comm ]; then
    log_error "PCSCD socket not found. Make sure PCSCD is running on the host and socket is mounted."
    log_error "You may need to start PCSCD on the host with: sudo systemctl start pcscd"
    sleep 5
    exit 1
fi

log_info "Starting NFC Reader application..."
cd /app 
python nfc_reader.py

# Wait a while to avoid docker restarting the container immediately
log_error "NFC Reader application exited, probably due to an error."
log_info "Waiting for 65 seconds before exiting..."
sleep 65