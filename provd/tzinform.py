# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Return the current UTC offset and DST rules of arbitrary timezones.

"""
import os.path


class TimezoneNotFoundError(Exception):
    pass


class Time:
    def __init__(self, raw_seconds):
        self._raw_seconds = raw_seconds

    @property
    def as_seconds(self):
        return self._raw_seconds

    @property
    def as_minutes(self):
        return self._raw_seconds // 60

    @property
    def as_hours(self):
        return self._raw_seconds // 3600

    @property
    def as_hms(self):
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
        else:
            return self._compute_positive_hms()

    def _compute_positive_hms(self):
        seconds = abs(self._raw_seconds)
        return [seconds // 3600, seconds // 60 % 60, seconds % 60]


class TextTimezoneInfoDB:
    """Instances of TextTimeZoneInfoDB return timezone information read from a
    text file. The file format is the same as the one created by default for
    the tzdataexport tool.
    """

    _TZ_DEFAULT_FILENAME = os.path.join(os.path.dirname(__file__), 'tzinform/tzdatax')

    def __init__(self, filename=None):
        if filename is None:
            filename = self._TZ_DEFAULT_FILENAME
        self._read_file(filename)

    def _read_file(self, filename):
        fobj = open(filename)
        try:
            self._db = {}
            for line in fobj:
                if line and not line.startswith('#'):
                    name, offset, dst_rule = line.rstrip().split()
                    self._db[name] = {
                        'utcoffset': Time(int(offset)),
                        'dst': self._parse_dst_rule(dst_rule),
                    }
        finally:
            fobj.close()

    @classmethod
    def _parse_dst_rule(cls, string: str):
        if string == '-':
            return None

        tokens = string.split(';')
        return {
            'start': cls._parse_dst_change(tokens[0]),
            'end': cls._parse_dst_change(tokens[1]),
            'save': Time(int(tokens[2])),
            'as_string': string,
        }

    @classmethod
    def _parse_dst_change(cls, string: str):
        tokens = string.split('/')
        return {
            'month': int(tokens[0]),
            'day': tokens[1],
            'time': Time(int(tokens[2]))
        }

    def get_timezone_info(self, timezone_name):
        """Return timezone information for the timezone named timezone_name.
        
        The method returns a dictionary with the following key:
        - 'utcoffset':    the offset from UTC as a Time object
        - 'dst':          a dictionary containing the DST rules, or None if the timezone has no DST
          - 'start'       a dictionary containing the DST start rule
            - 'month'     the month number
            - 'day'       the day. Can be either something like 'D24' or 'W1.6'
            - 'time'      the time of the day, as a Time object
          - 'end'         a dictionary containing the DST end rule
          - 'save'        an offset from standard time as a Time object
          - 'as_string'   the original DST string
        
        Raise a TimezoneNotFoundError is no information for the timezone is
        found.
        """
        try:
            return self._db[timezone_name]
        except KeyError:
            raise TimezoneNotFoundError(timezone_name)


class DefaultTimezoneInfoDB:
    """Instances of DefaultTimezoneInfoDB returns timezone information from
    another TimezoneInfoDB, or a default timezone information in the case the
    timezone can't be found.
    
    >>> tz_db = DefaultTimezoneInfoDB('Europe/Paris', TextTimezoneInfoDB())
    >>> tz_db.get_timezone_info('Moon/Sea_of_Tranquility')['utcoffset'].as_hours
    1
    """
    def __init__(self, default_tz, db):
        self.db = db
        self.default = db.get_timezone_info(default_tz)

    def get_timezone_info(self, timezone_name):
        try:
            return self.db.get_timezone_info(timezone_name)
        except TimezoneNotFoundError:
            return self.default


get_timezone_info = TextTimezoneInfoDB().get_timezone_info


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
