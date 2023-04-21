# Copyright 2014-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from unittest.mock import Mock, sentinel

from hamcrest import assert_that, equal_to, is_
from provd.app import ApplicationConfigureService
from provd.services import InvalidParameterError


class TestAppConfigureService(unittest.TestCase):

    def setUp(self):
        self.app = Mock()
        self.service = ApplicationConfigureService(Mock(), {}, self.app)

    def test_get_nat(self):
        self.app.nat = sentinel.nat

        value = self.service.get('NAT')

        assert_that(value, is_(sentinel.nat))

    def test_set_nat_valid_values(self):
        for value in [0, 1]:
            self.service.set('NAT', str(value))
            assert_that(self.app.nat, equal_to(value))

    def test_set_nat_invalid_values(self):
        for value in ['-1', '2', 'foobar']:
            self.assertRaises(InvalidParameterError, self.service.set, 'NAT', value)

    def test_set_nat_to_none(self):
        self.service.set('NAT', None)
        assert_that(self.app.nat, equal_to(0))
