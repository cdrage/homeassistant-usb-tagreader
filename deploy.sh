#!/bin/bash

# NFC Reader Remote Deployment Script
# Deploys and runs the NFC reader container on a remote host

set -e

REGISTRY="registry.apps.lasath.com"
IMAGE_NAME="nfc-reader"
REMOTE_HOST="$1"
TAG="${2:-latest}"
FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$TAG"
CONTAINER_NAME="nfc-reader"

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

print_usage() {
    echo "Usage: $0 <REMOTE_HOST> [TAG]"
    echo ""
    echo "Arguments:"
    echo "  REMOTE_HOST    SSH hostname or IP address of remote host"
    echo "  TAG            Docker image tag to deploy (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0 pi.local                    # Deploy latest tag to pi.local"
    echo "  $0 192.168.1.100 v1.0         # Deploy v1.0 tag to IP address"
    echo "  $0 hostname --logs             # View logs from hostname"
    echo "  $0 hostname --status           # Check status on hostname"
}

# Check if SSH is available
check_ssh() {
    if ! command -v ssh &> /dev/null; then
        log_error "SSH is not installed or not in PATH"
        exit 1
    fi
}

# Test SSH connection
test_ssh_connection() {
    log_info "Testing SSH connection to $REMOTE_HOST..."
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$REMOTE_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
        log_error "Cannot connect to $REMOTE_HOST via SSH"
        log_error "Please ensure:"
        log_error "  1. SSH key is set up for passwordless authentication"
        log_error "  2. Host $REMOTE_HOST is reachable"
        log_error "  3. SSH service is running on the remote host"
        exit 1
    fi
    log_info "SSH connection verified"
}

# Deploy and run container on remote host
deploy_container() {
    log_info "Deploying NFC Reader container to $REMOTE_HOST..."
    
    # Create deployment script to run on remote host
    local deploy_script=$(cat <<EOF
#!/bin/bash
set -e

echo "Stopping existing container if running..."
if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    docker stop "$CONTAINER_NAME"
fi

echo "Removing existing container if it exists..."
if docker ps -aq -f name="$CONTAINER_NAME" | grep -q .; then
    docker rm "$CONTAINER_NAME"
fi

echo "Pulling latest image: $FULL_IMAGE_NAME"
docker pull "$FULL_IMAGE_NAME"

echo "Starting NFC Reader container..."
docker run -d \\
    --name "$CONTAINER_NAME" \\
    --privileged \\
    --device=/dev/bus/usb:/dev/bus/usb \\
    -v /dev:/dev \\
    --restart unless-stopped \\
    "$FULL_IMAGE_NAME"

echo "Container deployed successfully!"
echo "Container logs:"
docker logs "$CONTAINER_NAME"
EOF
)
    
    # Execute deployment script on remote host
    ssh "$REMOTE_HOST" "bash -s" <<< "$deploy_script"
}

# Show container status
show_status() {
    log_info "Checking container status on $REMOTE_HOST..."
    ssh "$REMOTE_HOST" "docker ps -f name=$CONTAINER_NAME --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
}

# Show container logs
show_logs() {
    log_info "Showing container logs from $REMOTE_HOST..."
    ssh "$REMOTE_HOST" "docker logs -f $CONTAINER_NAME"
}

# Validate arguments
if [[ -z "$REMOTE_HOST" ]]; then
    log_error "Remote host is required"
    print_usage
    exit 1
fi

# Parse command line arguments
case "${2:-}" in
    -h|--help)
        print_usage
        exit 0
        ;;
    --logs)
        check_ssh
        test_ssh_connection
        show_logs
        exit 0
        ;;
    --status)
        check_ssh
        test_ssh_connection
        show_status
        exit 0
        ;;
esac

# Handle help flag as first argument
case "${1:-}" in
    -h|--help)
        print_usage
        exit 0
        ;;
esac

# Main execution
log_info "Starting deployment of NFC Reader to $REMOTE_HOST..."
log_info "Image: $FULL_IMAGE_NAME"

check_ssh
test_ssh_connection
deploy_container
show_status

log_info "Deployment completed successfully!"
log_info "To view logs: $0 $REMOTE_HOST --logs"
log_info "To check status: $0 $REMOTE_HOST --status"