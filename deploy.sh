#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="yauheni"
REMOTE_HOST="userver.local"
REMOTE_DIR="cv-creator"
IMAGE_NAME="cv-creator-web"
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

echo "=== CV Creator Deploy to ${REMOTE_HOST} ==="

# Build locally
echo "Building image..."
docker build --platform linux/amd64 -t "$IMAGE_NAME" .

# Use a single SSH control socket to avoid repeated password prompts
SSH_SOCK="/tmp/deploy-cv-creator-$$"
ssh -fNM -S "$SSH_SOCK" "$SSH_TARGET"
trap 'ssh -S "$SSH_SOCK" -O exit "$SSH_TARGET" 2>/dev/null' EXIT

ssh_cmd() { ssh -S "$SSH_SOCK" "$SSH_TARGET" "$@"; }
scp_cmd() { scp -o "ControlPath=$SSH_SOCK" "$@"; }

# Transfer image
echo "Transferring image to ${REMOTE_HOST}..."
docker save "$IMAGE_NAME" | ssh_cmd "docker load"

# Copy compose file and .env
echo "Syncing compose file and .env..."
ssh_cmd "mkdir -p ~/${REMOTE_DIR}"
scp_cmd docker-compose.prod.yml "${SSH_TARGET}:~/${REMOTE_DIR}/docker-compose.yml"
scp_cmd .env "${SSH_TARGET}:~/${REMOTE_DIR}/.env"

# Stop existing services and start fresh
echo "Starting services on ${REMOTE_HOST}..."
ssh_cmd "cd ~/${REMOTE_DIR} && docker compose down && docker compose up -d"

echo ""
echo "Deployed! Service available at http://${REMOTE_HOST}:8952"
