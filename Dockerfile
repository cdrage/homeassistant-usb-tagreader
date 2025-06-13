ARG PYTHON_VARIANT=slim
ARG DEV_MODE=false
ARG PYTHON_RELEASE=3.11
FROM python:${PYTHON_RELEASE}${PYTHON_VARIANT:+-$PYTHON_VARIANT}

# Re-declare after FROM to make it available in subsequent layers
ARG DEV_MODE=false
ARG PYTHON_RELEASE

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
RUN <<EOF
if [ "$DEV_MODE" = "true" ]; then
    set -e

    echo "Installing development packages..."
    apt-get update
    apt-get install -y sudo pcscd vsmartcard-vpcd vsmartcard-vpicc python3-virtualsmartcard
    rm -rf /var/lib/apt/lists/*

    # We have to use the virtualsmartcard package from debian,
    # because it does not seem to be available on PyPI.
    # But that package gets installed to the system python installation,
    # so we create a symlink to make it available to the image-provided
    # python installation.
    ln -s /usr/lib/python3/site-packages/virtualsmartcard /usr/local/lib/python${PYTHON_RELEASE}/site-packages/

    echo "nfcuser ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/nfcuser

    echo "Development packages installed successfully"
else
    echo "Skipping development packages (DEV_MODE='$DEV_MODE')"
fi
EOF

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

# Switch to non-root user
USER nfcuser

# Run the startup script
CMD ["./start.sh"]