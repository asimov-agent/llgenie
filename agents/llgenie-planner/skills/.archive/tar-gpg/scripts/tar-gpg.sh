#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <file_or_directory> [output_name]"
    echo "  Creates <output>.tar.gpg encrypted with a passphrase prompt"
    exit 1
fi

INPUT="$1"
BASENAME="${INPUT%/}"
BASENAME="${BASENAME##*/}"
OUTPUT="${2:-$BASENAME}.tar.gpg"

if [[ ! -e "$INPUT" ]]; then
    echo "Error: '$INPUT' not found"
    exit 1
fi

echo "Encrypting '$INPUT' -> '$OUTPUT'"
tar cf - -C "$(dirname "$INPUT")" "$BASENAME" | gpg --symmetric --cipher-algo AES256 --output "$OUTPUT"

echo "Done: $OUTPUT, removing '$INPUT'"
rm -rf "$INPUT"
