FROM python:3.11-slim

# Install system dependencies for PCSC
RUN apt-get update && apt-get install -y \
    libpcsclite-dev \
    pcscd \
    python3-pyscard \
    libusb-1.0-0-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY nfc_reader.py .

# Create a non-root user and add to dialout group for USB access
RUN useradd -m -u 1000 nfcuser && \
    usermod -a -G dialout nfcuser && \
    chown -R nfcuser:nfcuser /app
USER nfcuser

# Run the application
CMD ["python", "nfc_reader.py"]