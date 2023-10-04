# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


from wazo_test_helpers import bus


class BusClientWrapper:
    def __init__(self):
        self.host = None
        self.port = None
        self.exchange_name = None
        self.exchange_type = None
        self._bus = None

    def __getattr__(self, attr):
        if self._bus is None:
            self._bus = self._create_client()
        return getattr(self._bus, attr)

    def _reset_bus(self):
        self._bus = None

    def _create_client(self):
        if (
            not self.port
            or not self.host
            or not self.exchange_name
            or not self.exchange_type
        ):
            return None
        return bus.BusClient.from_connection_fields(
            host=self.host,
            port=self.port,
            exchange_name=self.exchange_name,
            exchange_type=self.exchange_type,
        )

    def send_tenant_deleted(self, tenant_uuid, slug='slug'):
        if self.exchange_type != 'headers':
            raise NotImplementedError()

        event = {
            'name': 'auth_tenant_deleted',
            'data': {'uuid': tenant_uuid, 'slug': slug},
        }
        self.publish(event, headers={'name': event['name']})


BusClient = BusClientWrapper()


def setup_bus(host, port):
    BusClient.host = host
    BusClient.port = port
    BusClient.exchange_name = 'wazo-headers'
    BusClient.exchange_type = 'headers'
