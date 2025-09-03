# Copyright 2010-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Return the current UTC offset and DST rules of arbitrary timezones.
"""
from __future__ import annotations

import logging
import zoneinfo
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Union
from zoneinfo._zoneinfo import _parse_tz_str, _TZStr

logger = logging.getLogger(__name__)


class DSTChangeDict(TypedDict):
    month: int
    day: str
    time: Time


class DSTRuleDict(TypedDict):
    start: DSTChangeDict
    end: DSTChangeDict
    save: Time
    as_string: str


class TimeZoneInfoDict(TypedDict):
    utcoffset: Time
    dst: Union[DSTRuleDict, None]


class TimezoneNotFoundError(Exception):
    pass


class Time:
    def __init__(self, raw_seconds: int) -> None:
        self._raw_seconds = raw_seconds

    @property
    def as_seconds(self) -> int:
        return self._raw_seconds

    @property
    def as_minutes(self) -> int:
        return self._raw_seconds // 60

    @property
    def as_hours(self) -> int:
        return self._raw_seconds // 3600

    @property
    def as_hms(self) -> list[int]:
        """Return the time decomposed into hours, minutes and seconds.

        Note that if the time is negative, only the leftmost non-zero value will be
        negative.

        >>> Time(3602).as_hms   # 1 hour, 0 minutes and 2 seconds
        [1, 0, 2]
        >>> Time(-3602).as_hms  # -(1 hour, 0 minutes and 2 seconds)
        [-1, 0, 2]
        >>> Time(-2).as_hms
        [0, 0, -2]
        """
        if self._raw_seconds < 0:
            result = self._compute_positive_hms()
            for i in range(len(result)):
                if result[i]:
                    result[i] = -result[i]
                    break
            return result
        return self._compute_positive_hms()

    def _compute_positive_hms(self) -> list[int]:
        seconds = abs(self._raw_seconds)
        return [seconds // 3600, seconds // 60 % 60, seconds % 60]

    def __eq__(self, other: object):
        return (
            isinstance(other, self.__class__)
            and self._raw_seconds == other._raw_seconds
        )


class DefaultTimezoneInfoDB:
    """Instances of DefaultTimezoneInfoDB returns timezone information from
    another TimezoneInfoDB, or a default timezone information in the case the
    timezone can't be found.

    >>> tz_db = DefaultTimezoneInfoDB('Europe/Paris', TextTimezoneInfoDB())
    >>> tz_db.get_timezone_info('Moon/Sea_of_Tranquility')['utcoffset'].as_hours
    1
    """

    def __init__(self, default_tz: str, db: TextTimezoneInfoDB) -> None:
        self.db = db
        self.default = db.get_timezone_info(default_tz)

    def get_timezone_info(self, timezone_name: str) -> TimeZoneInfoDict:
        try:
            return self.db.get_timezone_info(timezone_name)
        except TimezoneNotFoundError:
            return self.default


class NativeTimezoneInfoDB:
    """Instances of NativeTimeZoneInfoDB return timezone information from the native
    Python ZoneInfo module.
    """

    _native_offsets: dict[str, _TZStr] = {}

    def __init__(self) -> None:
        available_zones = zoneinfo.available_timezones()
        for tz_path in zoneinfo.TZPATH:
            basepath = Path(tz_path)
            if basepath.exists():
                break

        for z in available_zones:
            filename = basepath / z
            try:
                with open(filename, "rb") as zobj:
                    content = zobj.readlines()
            except OSError:
                logger.error('Could not read file %s', filename)
                continue
            try:
                self._native_offsets[z] = _parse_tz_str(
                    content[-1].decode("ascii").strip("\n")
                )
            except (ValueError, IndexError) as e:
                logger.error('Could not parse tz: %s', e)
                continue

    def get_timezone_info(self, timezone_name: str) -> TimeZoneInfoDict:
        zone = self._native_offsets.get(timezone_name)
        if not zone:
            logger.debug('Could not find zone for %s', timezone_name)
            raise TimezoneNotFoundError(timezone_name)

        seconds = int(zone.std.utcoff.total_seconds())
        transitions = zone.transitions(datetime.now().year)
        dst_start = datetime.fromtimestamp(transitions[0])
        dst_end = datetime.fromtimestamp(transitions[1])
        return {
            'utcoffset': Time(seconds),
            'dst': DSTRuleDict(
                start=DSTChangeDict(
                    month=dst_start.month,
                    day=f"D{dst_start.day}",
                    time=Time(
                        dst_start.second + 60 * dst_start.minute + 3600 * dst_start.hour
                    ),
                ),
                end=DSTChangeDict(
                    month=dst_end.month,
                    day=f"D{dst_end.day}",
                    time=Time(
                        dst_end.second + 60 * dst_end.minute + 3600 * dst_end.hour
                    ),
                ),
                save=Time(zone.dst.dstoff.total_seconds()),
                as_string=str(zone),
            ),
        }


get_timezone_info = NativeTimezoneInfoDB().get_timezone_info
# NOTE(afournier): remove in Jan 2028
# Compatibility layer, since some plugins used directly TextTimezoneInfoDB
TextTimezoneInfoDB = NativeTimezoneInfoDB


def week_start_on_monday(weekday: int) -> int:
    """Convert weekday so that monday is the first day of the week (instead of sunday).

    >>> week_start_on_monday(1)  # sunday is now the last day of the week
    7
    >>> week_start_on_monday(2)  # ...and monday is the first
    1
    """
    return (weekday - 1 + 6) % 7 + 1


if __name__ == '__main__':
    import doctest

    doctest.testmod(verbose=True)
