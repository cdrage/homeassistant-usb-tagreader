FROM python:3.11-slim

# Install system dependencies for libnfc
RUN apt-get update && apt-get install -y \
    libnfc6 \
    libnfc-bin \
    libnfc-dev \
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

# Create a non-root user for security
RUN useradd -m -u 1000 nfcuser && chown -R nfcuser:nfcuser /app
USER nfcuser

# Run the application
CMD ["python", "nfc_reader.py"]