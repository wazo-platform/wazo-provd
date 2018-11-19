.PHONY: test-setup test egg-info pull-images provd-test provd

PROVD_DIR ?= ../


test-setup: egg-info pull-images provd

pull-images:
	docker pull wazopbx/wait
	docker pull swaggerapi/swagger-validator

provd:
	docker pull python:2.7.13-stretch
	docker build -t wazopbx/xivo-provd $(PROVD_DIR)
	$(MAKE) provd-test

provd-test:
	docker build --no-cache -t xivo-provd-tests -f Dockerfile $(PROVD_DIR)

test:
	nosetests -x

egg-info:
	cd $(PROVD_DIR) && python setup.py egg_info
