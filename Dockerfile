FROM python:2.7.13-stretch
MAINTAINER Wazo Maintainers <dev@wazo.community>

# Install
ADD . /usr/src/xivo-provisioning
WORKDIR /usr/src/xivo-provisioning
RUN pip install -r requirements.txt
RUN python setup.py install

# Configure environment
RUN mkdir /var/cache/xivo-provd/
RUN mkdir -p /etc/xivo/provd/
RUN cp -r etc/xivo/provd/* /etc/xivo/provd/

# Fix the dropin.cache
RUN twistd --help-reactors

# Add an updated configuration file (updated by xivo-config template in a real engine)
ADD ./contribs/docker/provd.conf /etc/xivo/provd/provd.conf

# Add certificates
ADD ./contribs/docker/certs /usr/share/xivo-certs
WORKDIR /usr/share/xivo-certs
RUN openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -nodes -config openssl.cfg -days 3650


EXPOSE 8667
EXPOSE 8666
EXPOSE 69/udp

CMD ["twistd", "--nodaemon", "--no_save", "--pidfile=", "--reactor=epoll", "xivo-provd", "--stderr", "--verbose"]
