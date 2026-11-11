#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <file.tar.gpg>"
    echo "  Decrypts and extracts to the original folder name"
    exit 1
fi

INPUT="$1"
OUTPUT="${INPUT%.tar.gpg}"

if [[ ! -f "$INPUT" ]]; then
    echo "Error: '$INPUT' not found"
    exit 1
fi

echo "Decrypting '$INPUT' -> '$OUTPUT'"
gpg --decrypt "$INPUT" | tar xf -

echo "Done: extracted to '$OUTPUT', removing '$INPUT'"
rm -f "$INPUT"
