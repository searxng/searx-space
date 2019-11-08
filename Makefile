APP_NAME=searx/searxstats:latest
CONTAINER_NAME=searxstats
OUTPUT_FILENAME=instances.json

ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

DOCKER_INTERACTIVE_PARAM:=$(shell [ -t 0 ] && echo " -t -i")

qa:
	pylint searxstats

docker-build: ## Build the container
	docker build -t $(APP_NAME) .

docker-run:
	touch $(ROOT_DIR)/html/data/instances.json
	chgrp 1005 $(ROOT_DIR)/html/data/instances.json
	chmod 664 $(ROOT_DIR)/html/data/instances.json
	docker run $(DOCKER_INTERACTIVE_PARAM) --rm -v $(ROOT_DIR)/html/data:/usr/local/searx-instances/html/data --name="$(CONTAINER_NAME)" $(APP_NAME) -o html/data/$(OUTPUT_FILENAME) $(SEARX_URL) --all

webserver:
	cd $(ROOT_DIR)/html; python -m SimpleHTTPServer 8888
