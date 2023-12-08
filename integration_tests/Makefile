PROVD_DIR ?= ../

test-setup: egg-info provd provd-test db

provd:
	docker build -t wazoplatform/wazo-provd $(PROVD_DIR)

provd-test:
	docker build --no-cache -t wazo-provd-tests -f Dockerfile $(PROVD_DIR)

test:
	pytest -x -vvv

db:
	docker build --pull -f ../contribs/docker/Dockerfile-db -t wazoplatform/wazo-provd-db ..

egg-info:
	cd $(PROVD_DIR) && python3 setup.py egg_info

.PHONY: test-setup test egg-info provd-test provd
