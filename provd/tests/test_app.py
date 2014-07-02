# -*- coding: utf-8 -*-

# Copyright (C) 2014 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import unittest
from hamcrest import assert_that, equal_to, is_
from mock import Mock, sentinel
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
