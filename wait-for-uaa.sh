#!/bin/bash

export TEXTA_UAA_URL="${TEXTA_UAA_URL:-http://localhost:8080}"

# wait for server to start
until $(curl --output /dev/null --silent --head --fail "$TEXTA_UAA_URL/uaa"); do
    echo "Waiting for UAA server to run."
    sleep 5
done
echo "UAA server running."
