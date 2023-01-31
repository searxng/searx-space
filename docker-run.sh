ROOT_DIR=$(dirname $(realpath $0))
CONTAINER_NAME=searxstats
DOCKER_INTERACTIVE_PARAM=$([ -t 0 ] && echo " -t -i")
APP_NAME=searx/searxstats:latest
OUTPUT_FILENAME=instances.json

docker run $DOCKER_INTERACTIVE_PARAM \
    --rm \
    --network host \
    -v $ROOT_DIR/html/data:/usr/local/searxstats/html/data \
    -v $ROOT_DIR/cache:/usr/local/searxstats/cache \
    -e MMDB_FILENAME=/usr/local/searxstats/cache/dbip-country-lite.mmdb \
    --name="$CONTAINER_NAME" \
    $APP_NAME \
    --database sqlite:////usr/local/searxstats/cache/searxstats.db \
    --cache /usr/local/searxstats/cache \
    --output /usr/local/searxstats/html/data/$OUTPUT_FILENAME \
    "$@"
