FROM wazoplatform/wazo-provd

ENV PYTHONDONTWRITEBYTECODE='true'

COPY . /usr/src/wazo-provd
WORKDIR /usr/src/wazo-provd

RUN pip install -e . --config-settings editable_mode=compat
