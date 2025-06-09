FROM python:3.11-slim

# Install system dependencies for PCSC
RUN apt-get update && apt-get install -y \
    libpcsclite-dev \
    pcscd \
    pcsc-tools \
    python3-pyscard \
    libusb-1.0-0-dev \
    pkg-config \
    gcc \
    swig \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and startup script
COPY nfc_reader.py .
COPY start.sh .
RUN chmod +x start.sh

# Create a non-root user and add to dialout group for USB access
RUN useradd -m -u 1000 nfcuser && \
    usermod -a -G dialout nfcuser && \
    chown -R nfcuser:nfcuser /app

# Note: We need to run as root for PCSCD, then switch to nfcuser for the app
USER root

# Run the startup script
CMD ["./start.sh"]