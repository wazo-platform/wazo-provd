# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import Mock

from wazo_provd.services import (
    JsonConfigPersister,
    PersistentConfigurationServiceDecorator,
)


class TestPersistentConfigurationServiceDecorator(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.filename = os.path.join(directory.name, 'app.json')
        self.cfg_service = Mock(VIRTUAL_ATTRIBUTES={}, RESET_ON_NULL={'reset'})

    def _decorate(self) -> PersistentConfigurationServiceDecorator:
        return PersistentConfigurationServiceDecorator(
            self.cfg_service, JsonConfigPersister(self.filename)
        )

    def _stored(self) -> dict:
        with open(self.filename) as f:
            return json.load(f)

    def test_set_stores_the_value(self) -> None:
        self._decorate().set('reset', 'value')

        self.cfg_service.set.assert_called_once_with('reset', 'value')
        assert self._stored() == {'reset': 'value'}

    def test_set_null_drops_a_reset_on_null_value(self) -> None:
        service = self._decorate()
        service.set('reset', 'value')
        service.set('other', 'value')

        for value in [None, '']:
            service.set('reset', value)
            self.cfg_service.set.assert_called_with('reset', value)
            assert self._stored() == {'other': 'value'}

    def test_set_null_stores_other_values(self) -> None:
        self._decorate().set('other', None)

        assert self._stored() == {'other': None}

    # Stored by an earlier version, before null dropped the value.
    def test_set_null_drops_a_stored_null(self) -> None:
        with open(self.filename, 'w') as f:
            json.dump({'reset': None}, f)

        self._decorate().set('reset', None)

        assert self._stored() == {}

    def test_dropped_value_is_not_replayed(self) -> None:
        service = self._decorate()
        service.set('reset', 'value')
        service.set('reset', None)
        self.cfg_service.reset_mock()

        self._decorate()

        self.cfg_service.set.assert_not_called()
