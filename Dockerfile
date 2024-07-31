FROM python:3.9-slim-bullseye AS compile-image
LABEL maintainer="Wazo Maintainers <dev@wazo.community>"

RUN apt-get -q update
RUN apt-get -yq install gcc
RUN python -m venv /opt/venv
# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"

# Install
ADD . /usr/src/wazo-provd
WORKDIR /usr/src/wazo-provd
# incremental==24.7.0+ is downloaded automatically by twisted install
# but this version is incompatible with setuptools 58.1 from python:3.9-slim-bullseye
RUN pip install incremental==17.5.0
RUN pip install -r requirements.txt
RUN python setup.py install

# Install compatibility module for old plugins
RUN cp -r provd /opt/venv/lib/python3.9/site-packages/provd

FROM python:3.9-slim-bullseye AS build-image
COPY --from=compile-image /opt/venv /opt/venv

COPY ./etc/wazo-provd /etc/wazo-provd
RUN mkdir -p /var/cache/wazo-provd

EXPOSE 8667
EXPOSE 8666
EXPOSE 69/udp

# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"
CMD ["twistd", "--nodaemon", "--no_save", "--pidfile=", "wazo-provd", "--stderr", "--verbose"]
