FROM debian:latest

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -qq update
RUN apt-get -qq -y install apt-utils
RUN apt-get -qq -y install \
     build-essential \
     python \
     python-pip \
     git \
     libffi-dev \
     python-dev 

WORKDIR /root/
WORKDIR /root
RUN git clone https://github.com/xivo-pbx/xivo-provisioning.git
WORKDIR /root/xivo-provisioning
RUN pip install -U setuptools
RUN pip install -r requirements.txt
RUN python setup.py install
RUN mkdir /var/cache/xivo-provd/
RUN mkdir -p /etc/xivo/provd/
RUN cp -r etc/xivo/provd/* /etc/xivo/provd/

WORKDIR /root
RUN rm -fr /root/xivo-provisioning

# Fix the dropin.cache
RUN twistd --help-reactors

EXPOSE 8667
EXPOSE 8666
EXPOSE 69/udp

CMD twistd -no -r epoll xivo-provd -s -v
