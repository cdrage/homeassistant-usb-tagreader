#!/bin/bash

# NFC Reader Docker Build and Push Script

set -e

REGISTRY="registry.apps.lasath.com"
IMAGE_NAME="nfc-reader"
TAG="${1:-latest}"
FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$TAG"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

# Build Docker image
build_docker_image() {
    log_info "Building Docker image: $FULL_IMAGE_NAME"
    docker build -t "$FULL_IMAGE_NAME" .
    
    # Also tag as latest
    docker tag "$FULL_IMAGE_NAME" "$REGISTRY/$IMAGE_NAME:latest"
}

# Push to registry
push_to_registry() {
    log_info "Pushing image to registry: $FULL_IMAGE_NAME"
    docker push "$FULL_IMAGE_NAME"
    
    if [[ "$TAG" != "latest" ]]; then
        log_info "Pushing latest tag..."
        docker push "$REGISTRY/$IMAGE_NAME:latest"
    fi
}

# Main execution
log_info "Starting Docker build and push for NFC Reader..."

check_docker
build_docker_image
push_to_registry

log_info "Docker build and push completed successfully!"
log_info "Image available at: $FULL_IMAGE_NAME"