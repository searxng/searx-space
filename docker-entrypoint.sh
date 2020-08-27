#!/bin/sh

BASE_DIR="$(dirname -- "`readlink -f -- "$0"`")"

cd -- "$BASE_DIR"
set -e

export PATH=/opt/firefox:$PATH

/usr/bin/tor -f /usr/local/searxstats/torrc

pip3 install --upgrade -r requirements-update.txt
python3 -msearxstats $@
