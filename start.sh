#!/bin/bash

# Startup script for NFC Reader connecting to host PCSCD
echo "Connecting to host PCSCD daemon..."

# Check if we can connect to PCSCD socket
if [ ! -S /run/pcscd/pcscd.comm ]; then
    echo "ERROR: PCSCD socket not found. Make sure PCSCD is running on the host and socket is mounted."
    echo "You may need to start PCSCD on the host with: sudo systemctl start pcscd"
    sleep 5
    exit 1
fi

echo "Starting NFC Reader application..."
cd /app 
python nfc_reader.py

# Wait a while to avoid docker restarting the container immediately
echo "NFC Reader application exited, probably due to an error."
echo "Waiting for 65 seconds before exiting..."
sleep 65