FROM python:2.7-slim-buster AS compile-image
LABEL maintainer="Wazo Maintainers <dev@wazo.community>"

RUN apt-get -q update
RUN apt-get -yq install gcc
RUN pip install virtualenv
RUN python -m virtualenv /opt/venv
# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"

# Install
ADD . /usr/src/wazo-provd
WORKDIR /usr/src/wazo-provd
RUN pip install -r requirements.txt
RUN python setup.py install

FROM python:2.7-slim-buster AS build-image
COPY --from=compile-image /opt/venv /opt/venv

COPY ./etc/wazo-provd /etc/wazo-provd
RUN mkdir -p /var/cache/wazo-provd

EXPOSE 8667
EXPOSE 8666
EXPOSE 69/udp

# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"
CMD ["twistd", "--nodaemon", "--no_save", "--pidfile=", "wazo-provd", "--stderr", "--verbose"]
