# NFC Tag Reader

A Python application that uses libnfc to listen for NFC tags on USB NFC readers and print their contents.

## Features

- Automatically detects USB NFC readers
- Reads and displays NFC tag information including:
  - Tag type and identifier
  - NDEF capacity and length
  - NDEF records with data
- Comprehensive type hints throughout the codebase
- Dockerized for easy deployment across different machines
- Graceful shutdown handling

## Requirements

- USB NFC reader compatible with PCSC
- PCSC daemon (pcscd) running on the host system
- Docker and Docker Compose (for containerized deployment)
- Python 3.11+ (if running locally)

## Quick Start with Docker

**Important**: Before running the Docker container, ensure PCSC daemon is running on your host system:

```bash
# On Ubuntu/Debian:
sudo apt-get install pcscd pcsc-tools
sudo systemctl start pcscd
sudo systemctl enable pcscd  # Optional: start on boot

# Verify PCSC is working:
pcsc_scan
```

1. Build and run the container:
```bash
docker-compose up --build
```

2. The application will start listening for NFC tags. Place a tag near your NFC reader to see its contents.

3. To stop the application:
```bash
docker-compose down
```

## Local Development

1. Install system dependencies (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install pcscd pcsc-tools libpcsclite-dev libusb-1.0-0-dev pkg-config
sudo systemctl start pcscd
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python nfc_reader.py
```

## Docker Build Options

To build the Docker image manually:
```bash
docker build -t nfc-reader .
```

To run the container manually:
```bash
docker run -v /run/pcscd:/run/pcscd nfc-reader
```

## Troubleshooting

- **PCSCD socket not found**: Ensure PCSC daemon is running on the host with `sudo systemctl start pcscd`
- **No NFC readers found**: Ensure your NFC reader is connected and recognized by PCSC with `pcsc_scan`
- **Permission errors**: If you encounter socket permission issues, ensure the container user can access the PCSC socket
- **Tag not detected**: Make sure the tag is placed close enough to the reader and is compatible

## Supported NFC Tags

The application supports various NFC tag types and will attempt to read NDEF records when available.