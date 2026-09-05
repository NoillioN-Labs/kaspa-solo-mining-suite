#!/bin/sh
set -e

# Fix permissions on the mounted volume
if [ -d "/app/data" ]; then
    chmod 0777 /app/data
fi

# Execute the main kaspad binary with provided arguments
exec kaspad "$@"
