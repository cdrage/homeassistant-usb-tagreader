ARG PYTHON_VARIANT=slim
ARG DEV_MODE=false
FROM python:3.11${PYTHON_VARIANT:+-$PYTHON_VARIANT}

# Install system dependencies for PCSC (client libraries only)
RUN apt-get update && apt-get install -y \
    libpcsclite-dev \
    libpcsclite1 \
    pcsc-tools \
    python3-pyscard \
    libusb-1.0-0-dev \
    pkg-config \
    gcc \
    swig \
    procps

# Conditionally install sudo and vsmartcard for development only
RUN if [ "$DEV_MODE" = "true" ]; then \
        apt-get update && \
        apt-get install -y sudo pcscd vsmartcard-vpcd vsmartcard-vpicc && \
        echo "nfcuser ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/nfcuser; \
    fi

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and startup script
COPY *.py .
COPY start.sh .
RUN chmod +x start.sh

# Create a non-root user for running the application
RUN useradd -m -u 1000 -s /bin/bash nfcuser && \
    chown -R nfcuser:nfcuser /app


# Clean up package lists
RUN rm -rf /var/lib/apt/lists/*

# Switch to non-root user
USER nfcuser

# Run the startup script
CMD ["./start.sh"]