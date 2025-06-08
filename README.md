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

- USB NFC reader compatible with libnfc
- Docker and Docker Compose (for containerized deployment)
- Python 3.11+ (if running locally)

## Quick Start with Docker

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
sudo apt-get install libnfc6 libnfc-bin libnfc-dev libusb-1.0-0-dev pkg-config
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
docker run --privileged --device=/dev/bus/usb:/dev/bus/usb -v /dev:/dev nfc-reader
```

## Troubleshooting

- **No NFC readers found**: Ensure your NFC reader is connected and recognized by the system
- **Permission errors**: The Docker container runs with privileged access to access USB devices
- **Tag not detected**: Make sure the tag is placed close enough to the reader and is compatible

## Supported NFC Tags

The application supports various NFC tag types and will attempt to read NDEF records when available.