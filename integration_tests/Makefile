.PHONY: test-setup test egg-info pull-images provd-test provd

PROVD_DIR ?= ../


test-setup: egg-info pull-images provd

pull-images:
	docker pull wazopbx/wait
	docker pull trinitronx/python-simplehttpserver
	docker pull wazopbx/wazo-auth-mock

provd:
	docker build --pull -t wazopbx/wazo-provd $(PROVD_DIR)
	$(MAKE) provd-test

provd-test:
	docker build --no-cache -t wazo-provd-tests -f Dockerfile $(PROVD_DIR)

test:
	nosetests -x

egg-info:
	cd $(PROVD_DIR) && python setup.py egg_info
