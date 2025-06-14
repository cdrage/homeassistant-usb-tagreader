#!/bin/bash

# NFC Reader Python Linting and Validation Script

set -e

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

# Check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
}

# Run Python linting and validation
run_python_checks() {
    log_info "Running Python syntax check..."
    python3 -m py_compile nfc_reader.py
    
    log_info "Running Black code formatter check..."
    if ! black --check --quiet nfc_reader.py; then
        log_warn "Code formatting issues found. Running Black formatter..."
        black nfc_reader.py
        log_info "Code formatted successfully"
    else
        log_info "Code formatting is correct"
    fi
    
    log_info "Running Flake8 linting..."
    flake8 --max-line-length=100 --ignore=E203,W503 nfc_reader.py || {
        log_error "Linting failed"
        exit 1
    }
    
    log_info "Running MyPy type checking..."
    mypy --ignore-missing-imports nfc_reader.py || {
        log_error "Type checking failed"
        exit 1
    }
    
    log_info "Running Pylint analysis..."
    pylint --disable=missing-module-docstring,missing-function-docstring nfc_reader.py || {
        log_warn "Pylint found some issues, but continuing..."
    }
}

# Main execution
log_info "Starting Python validation for NFC Reader..."

check_python
run_python_checks

log_info "Python validation completed successfully!"