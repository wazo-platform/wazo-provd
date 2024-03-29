PROVD_DIR ?= ../
DOCKER_DIR ?= docker

test-setup: egg-info provd provd-test

provd:
	docker build --pull -t wazoplatform/wazo-provd $(PROVD_DIR)

provd-test:
	docker build --no-cache -t wazo-provd-tests -f Dockerfile $(PROVD_DIR)
	docker build --no-cache -t wazo-provd-plugin-server -f $(DOCKER_DIR)/Dockerfile-http-server $(DOCKER_DIR)

test:
	pytest -x -vvv

egg-info:
	cd $(PROVD_DIR) && python setup.py egg_info

.PHONY: test-setup test egg-info provd-test provd
