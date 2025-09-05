# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, call, mock_open, patch

from hamcrest import assert_that, calling, empty, has_entries, not_, raises

from wazo_provd.tzinform import NativeTimezoneInfoDB, Time, TimezoneNotFoundError


class TestNativeTimezoneInfoDB(unittest.TestCase):
    @patch('wazo_provd.tzinform.zoneinfo.available_timezones')
    @patch('wazo_provd.tzinform.Path')
    @patch('wazo_provd.tzinform._parse_tz_str')
    def test_init_success(
        self,
        mock_parse_tz_str: MagicMock,
        mock_path: MagicMock,
        mock_zoneinfo_available_timezones: MagicMock,
    ):
        mock_zoneinfo_available_timezones.return_value = ['test1', 'test2']
        mock_path.return_value.__truediv__.side_effect = lambda file: f'path/{file}'
        mock_path.return_value.exists = MagicMock()
        mock_path.return_value.exists.side_effect = [False, True]
        mock_value = b'l1\nl2\nl3\nl4\n'
        with patch(
            'wazo_provd.tzinform.open', mock_open(read_data=mock_value)
        ) as m_patch:
            NativeTimezoneInfoDB()
            assert m_patch.call_args_list == [
                call('path/test1', 'rb'),
                call('path/test2', 'rb'),
            ]
            mock_parse_tz_str.assert_called()

    @patch('wazo_provd.tzinform.zoneinfo.available_timezones')
    @patch('wazo_provd.tzinform.Path')
    @patch('wazo_provd.tzinform._parse_tz_str')
    def test_init_no_tz_files(
        self,
        mock_parse_tz_str: MagicMock,
        mock_path: MagicMock,
        mock_zoneinfo_available_timezones: MagicMock,
    ):
        mock_zoneinfo_available_timezones.return_value = []
        mock_path.return_value.exists = MagicMock()
        mock_path.return_value.exists.return_value = False
        with patch('wazo_provd.tzinform.open', mock_open()) as m_patch:
            NativeTimezoneInfoDB()
            m_patch.assert_not_called()
            mock_parse_tz_str.assert_not_called()

    @patch('wazo_provd.tzinform.zoneinfo.available_timezones')
    @patch('wazo_provd.tzinform.Path')
    @patch('wazo_provd.tzinform._parse_tz_str')
    def test_init_cannot_open_file(
        self,
        mock_parse_tz_str: MagicMock,
        mock_path: MagicMock,
        mock_zoneinfo_available_timezones: MagicMock,
    ):
        mock_zoneinfo_available_timezones.return_value = ['test1', 'test2']
        mock_path.return_value.__truediv__.side_effect = lambda file: f'path/{file}'

        mock_path.return_value.exists = MagicMock()
        mock_path.return_value.exists.return_value = True
        with patch('wazo_provd.tzinform.open', mock_open()) as m_patch:
            m_patch.side_effect = OSError('not found')
            NativeTimezoneInfoDB()
            mock_parse_tz_str.assert_not_called()

    @patch('wazo_provd.tzinform.zoneinfo.available_timezones')
    @patch('wazo_provd.tzinform.Path')
    @patch('wazo_provd.tzinform._parse_tz_str')
    def test_init_cannot_parse_tz_str(
        self,
        mock_parse_tz_str: MagicMock,
        mock_path: MagicMock,
        mock_zoneinfo_available_timezones: MagicMock,
    ):
        mock_zoneinfo_available_timezones.return_value = ['test1', 'test2']
        mock_path.return_value.__truediv__.side_effect = lambda file: f'path/{file}'

        mock_path.return_value.exists = MagicMock()
        mock_path.return_value.exists.return_value = True
        mock_value = b'l1\nl2\nl3\nl4\n'
        with patch(
            'wazo_provd.tzinform.open', mock_open(read_data=mock_value)
        ) as m_patch:
            mock_parse_tz_str.side_effect = [
                ValueError('invalid TZ str'),
                IndexError('no content'),
            ]
            NativeTimezoneInfoDB()
            # It should continue reading if an exception occurs
            assert m_patch.call_args_list == [
                call('path/test1', 'rb'),
                call('path/test2', 'rb'),
            ]

    @patch('wazo_provd.tzinform.zoneinfo.available_timezones')
    @patch('wazo_provd.tzinform.Path')
    @patch('wazo_provd.tzinform._parse_tz_str')
    def test_get_timezone_info_success(
        self,
        mock_parse_tz_str: MagicMock,
        mock_path: MagicMock,
        mock_zoneinfo_available_timezones: MagicMock,
    ):
        mock_zoneinfo_available_timezones.return_value = ['test1', 'test2']
        mock_path.return_value.__truediv__.side_effect = lambda file: f'path/{file}'

        mock_path.return_value.exists = MagicMock()
        mock_path.return_value.exists.return_value = True
        mock_value = b'l1\nl2\nl3\nl4\n'
        with patch(
            'wazo_provd.tzinform.open', mock_open(read_data=mock_value)
        ) as m_patch:
            mock_tz_result = MagicMock()
            mock_tz_result.transitions.return_value = (
                datetime(2025, 1, 2, 3, 4, 5).timestamp(),
                datetime(2025, 6, 7, 8, 9, 10).timestamp(),
            )
            mock_tz_result.dst.dstoff.total_seconds.return_value = 11
            mock_tz_result.std.utcoff.total_seconds.return_value = 12
            mock_parse_tz_str.return_value = mock_tz_result

            native_tz_db = NativeTimezoneInfoDB()

            assert m_patch.call_args_list == [
                call('path/test1', 'rb'),
                call('path/test2', 'rb'),
            ]
            result = native_tz_db.get_timezone_info('test1')
            assert_that(
                result,
                has_entries(
                    utcoffset=Time(12),
                    dst=has_entries(
                        start=has_entries(
                            month=1,
                            day="D2",
                            time=Time(3 * 3600 + 4 * 60 + 5),
                        ),
                        end=has_entries(
                            month=6,
                            day="D7",
                            time=Time(8 * 3600 + 9 * 60 + 10),
                        ),
                        save=Time(11),
                        as_string=not_(empty()),
                    ),
                ),
            )

    @patch('wazo_provd.tzinform.zoneinfo.available_timezones')
    def test_get_timezone_info_tz_not_found(
        self, mock_zoneinfo_available_timezones: MagicMock
    ):
        mock_zoneinfo_available_timezones.return_value = []

        native_tz_db = NativeTimezoneInfoDB()
        native_tz_db._native_offsets = {}
        assert_that(
            calling(native_tz_db.get_timezone_info).with_args('test1'),
            raises(TimezoneNotFoundError),
        )
