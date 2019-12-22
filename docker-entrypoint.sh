#!/bin/sh

BASE_DIR="$(dirname -- "`readlink -f -- "$0"`")"

cd -- "$BASE_DIR"
set -e

/usr/bin/tor -f /usr/local/searxstats/torrc

python3 -msearxstats $@
