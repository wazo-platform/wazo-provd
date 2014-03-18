# -*- coding: utf-8 -*-

# Copyright (C) 2013-2014 Avencall
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
from provd.rest.pycli import helpers


class TestHelpers(unittest.TestCase):

    def test_are_plugins_installed_missing(self):
        installed_plugins = set()

        res = helpers._are_plugins_installed(['foo'], installed_plugins)

        self.assertFalse(res)

    def test_are_plugins_installed(self):
        installed_plugins = set(['foo'])

        res = helpers._are_plugins_installed(['foo'], installed_plugins)

        self.assertTrue(res)
