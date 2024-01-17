# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os

from wazo_provd_client import Client
from wazo_test_helpers import until
from wazo_test_helpers.asset_launching_test_case import (
    AssetLaunchingTestCase,
    NoSuchPort,
    NoSuchService,
)

from provd.database.helpers import init_db

from .database import SynchronousDatabaseAdapter
from .wait_strategy import NoWaitStrategy, WaitStrategy

API_VERSION = '0.2'

DB_URI = 'postgresql://wazo-provd:Secr7t@127.0.0.1:{port}'

VALID_TOKEN = 'valid-token'
INVALID_TOKEN = 'invalid-token'
INVALID_TENANT = '00000000-0000-4000-8000-999999999999'
VALID_TOKEN_MULTITENANT = 'valid-token-multitenant'
MAIN_TENANT = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1'
SUB_TENANT_1 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee2'
SUB_TENANT_2 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee3'


class ClientCreateException(Exception):
    def __init__(self, client_name):
        super().__init__(f'Could not create client {client_name}')


class WrongClient:
    def __init__(self, client_name):
        self.client_name = client_name

    def __getattr__(self, member):
        raise ClientCreateException(self.client_name)


class _BaseIntegrationTest(AssetLaunchingTestCase):
    assets_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
    )

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.set_client()

    @classmethod
    def set_client(cls):
        cls._client = cls.make_provd(VALID_TOKEN_MULTITENANT)

    @classmethod
    def make_provd(cls, token: str) -> Client:
        return Client(
            '127.0.0.1',
            port=cls.service_port(8666, 'provd'),
            version=API_VERSION,
            prefix=None,
            https=False,
            token=token,
        )

    @classmethod
    def make_db_session(cls) -> SynchronousDatabaseAdapter | WrongClient:
        try:
            port = cls.service_port(5432, 'postgres')
        except (NoSuchService, NoSuchPort):
            return WrongClient('postgres')
        connection_pool = init_db(DB_URI.format(port=port))
        return SynchronousDatabaseAdapter(connection_pool)

    @classmethod
    def start_postgres_service(cls) -> None:
        cls.asset_cls.start_service('postgres')
        cls._Session = cls.asset_cls.make_db_session()

        def db_is_up() -> bool:
            try:
                cls._Session.execute('SELECT 1')
            except Exception:
                return False
            return True

        until.true(db_is_up, tries=60)

    @classmethod
    def stop_postgres_service(cls) -> None:
        cls._Session.close()
        cls.asset_cls.stop_service('postgres')


class BaseIntegrationTest(_BaseIntegrationTest):
    asset = 'base'
    service = 'provd'
    wait_strategy = WaitStrategy()


class DBIntegrationTest(_BaseIntegrationTest):
    asset = 'database'
    service = 'postgres'
    wait_strategy: WaitStrategy = NoWaitStrategy()
