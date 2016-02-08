FROM python:2.7.9
MAINTAINER XiVO Team "dev@avencall.com"

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

EXPOSE 8667
EXPOSE 8666
EXPOSE 69/udp

CMD ["twistd", "-no", "-r", "epoll", "xivo-provd", "-s", "-v"]
