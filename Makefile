APP_NAME=searx/searxstats:latest

ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

qa:
	pylint searxstats tests
	python3 -m pytest tests -vv

docker-build: # Build the container
	docker build -t $(APP_NAME) .

docker-run: # Run the container
	# instances.json
	mkdir -p $(ROOT_DIR)/html/data
	touch $(ROOT_DIR)/html/data/instances.json
	chgrp 1005 $(ROOT_DIR)/html/data/instances.json
	chmod 664 $(ROOT_DIR)/html/data/instances.json
	# cache
	mkdir -p $(ROOT_DIR)/cache
	chgrp 1005 $(ROOT_DIR)/cache
	chmod 775 $(ROOT_DIR)/cache
	# run
	./docker-run.sh --all

webserver:
	mkdir -p html/data
	curl -o html/data/instances.json https://searx.space/data/instances.json
	python3 searxstats/render.py html/data/instances.json
	python3 -m http.server -d html 8889
