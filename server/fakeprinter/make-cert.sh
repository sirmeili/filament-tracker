#!/bin/sh
# Make a throwaway self-signed certificate for the fake printer's broker.
# It is for local testing only and is never committed (certs/ is ignored by git).
set -eu
# Git Bash on Windows would otherwise turn "/CN=..." into a file path.
export MSYS2_ARG_CONV_EXCL="*"
cd "$(dirname "$0")"
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=fake-printer" \
  -keyout certs/fake-printer.key -out certs/fake-printer.pem 2>/dev/null
# The broker runs as another user inside the container and must be able to read the key.
chmod 644 certs/fake-printer.key certs/fake-printer.pem
echo "Wrote certs/fake-printer.pem and certs/fake-printer.key"
