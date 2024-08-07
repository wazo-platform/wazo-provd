FROM python:3.9-slim-bullseye AS compile-image
LABEL maintainer="Wazo Maintainers <dev@wazo.community>"

RUN apt-get -q update
RUN apt-get -yq install gcc
RUN python -m venv /opt/venv
# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"

RUN echo "CHANGE SHOULD BE TAKEN FROM ZUUL"

# Install
COPY requirements.txt /usr/src/wazo-provd/
WORKDIR /usr/src/wazo-provd
# incremental==24.7.0+ is downloaded automatically by twisted install
# but this version is incompatible with setuptools 58.1 from python:3.9-slim-bullseye
RUN pip install incremental==17.5.0
RUN pip install -r requirements.txt

COPY setup.py /usr/src/wazo-provd/
COPY wazo_provd /usr/src/wazo-provd/wazo_provd
COPY twisted /usr/src/wazo-provd/twisted
# Install compatibility module for old plugins
COPY provd /usr/src/wazo-provd/provd
RUN python setup.py install

FROM python:3.9-slim-bullseye AS build-image
COPY --from=compile-image /opt/venv /opt/venv

COPY ./etc/wazo-provd /etc/wazo-provd
RUN mkdir -p /var/cache/wazo-provd

EXPOSE 8667
EXPOSE 8666
EXPOSE 69/udp

# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"
CMD "bash -c 'echo \"SHOULD BE VISIBLE\" && twistd --nodaemon --no_save --pidfile= wazo-provd --stderr --verbose'"
