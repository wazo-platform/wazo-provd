FROM python:2.7.13-stretch
MAINTAINER Wazo Maintainers <dev@wazo.community>

# Install
ADD . /usr/src/wazo-provd
WORKDIR /usr/src/wazo-provd
RUN pip install -r requirements.txt
RUN python setup.py install

# Configure environment
RUN mkdir /var/cache/wazo-provd/
RUN mkdir -p /etc/wazo-provd/
RUN cp -r etc/wazo-provd/* /etc/wazo-provd/

# Add certificates
ADD ./contribs/docker/certs /usr/share/xivo-certs
WORKDIR /usr/share/xivo-certs
RUN openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -nodes -config openssl.cfg -days 3650


EXPOSE 8667
EXPOSE 8666
EXPOSE 69/udp

CMD ["twistd", "--nodaemon", "--no_save", "--pidfile=", "wazo-provd", "--stderr", "--verbose"]
