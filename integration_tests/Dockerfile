FROM wazoplatform/wazo-provd

ENV PYTHONDONTWRITEBYTECODE='true'

COPY . /usr/src/wazo-provd
WORKDIR /usr/src/wazo-provd
RUN python3 setup.py develop
