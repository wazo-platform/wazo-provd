# -*- coding: utf-8 -*-

# Copyright (C) 2010-2014 Avencall
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
from provd.devices.ident import LastSeenUpdater, VotingUpdater


class TestLastSeenUpdater(unittest.TestCase):

    def setUp(self):
        self.updater = LastSeenUpdater()

    def test_last_seen_updater_set_on_conflict(self):
        dev_infos = [
            {'k1': 'v1'},
            {'k1': 'v2'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v2'})

    def test_last_seen_updater_noop_on_nonconflict(self):
        dev_infos = [
            {'k1': 'v1'},
            {'k2': 'v2'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1', 'k2': 'v2'})


class TestVotingUpdater(unittest.TestCase):

    def setUp(self):
        self.updater = VotingUpdater()

    def test_voting_updater_votes_for_only_if_only_one(self):
        dev_infos = [
            {'k1': 'v1'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1'})

    def test_voting_updater_votes_for_highest_1(self):
        dev_infos = [
            {'k1': 'v1'},
            {'k1': 'v1'},
            {'k1': 'v2'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1'})

    def test_voting_updater_votes_for_highest_2(self):
        dev_infos = [
            {'k1': 'v2'},
            {'k1': 'v1'},
            {'k1': 'v1'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1'})
