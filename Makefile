APP_NAME=searx/searxstats:latest

ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

qa:
	flake8 --max-line-length=120 searxstats tests
	pylint searxstats tests
	python -m pytest --cov-report html --cov=searxstats tests -vv

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
	cd $(ROOT_DIR)/html; python -m http.server 8889
