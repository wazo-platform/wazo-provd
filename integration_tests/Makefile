PROVD_DIR ?= ../

test-setup: egg-info provd provd-test

provd:
	docker build --pull -t wazopbx/wazo-provd $(PROVD_DIR)

provd-test:
	docker build --no-cache -t wazo-provd-tests -f Dockerfile $(PROVD_DIR)

test:
	pytest -x

egg-info:
	cd $(PROVD_DIR) && python setup.py egg_info

.PHONY: test-setup test egg-info provd-test provd
