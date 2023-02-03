# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import re
import socket
from typing import Any


_MAC_ADDR = re.compile(
    r'^[\da-fA-F]{1,2}([:-]?)(?:[\da-fA-F]{1,2}\1){4}[\da-fA-F]{1,2}$'
)
_NORMED_MAC = re.compile(r'^(?:[\da-f]{2}:){5}[\da-f]{2}$')
_NORMED_UUID = re.compile(r'^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$')


def decode_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {decode_bytes(k): decode_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode_value(v) for v in value]
    return decode_bytes(value)


def decode_bytes(value: Any, encoding: str = 'utf-8') -> str:
    """Take a value and if it is bytes it is a bytestring it decodes it.
    It is helpful for ensuring values are decoded in situations
    where it might be a string or bytes.
    """
    if isinstance(value, bytes):
        return value.decode(encoding)
    return value


def encode_bytes(value: str | bytes, encoding: str = 'utf-8') -> bytes:
    """Take a value and if it is a string encode it as bytes
    It is helpful for ensuring values are encoded in situations
    where it might be a string or bytes.
    """
    if isinstance(value, str):
        return value.encode(encoding)
    return value


def to_ip(ip_string: str) -> bytes:
    """Takes a human-readable IP address unicode string (i.e. '127.0.0.1')
    and return a 4-bytes string representation of it.

    >>> to_ip('255.255.255.255')
    '\xff\xff\xff\xff'
    >>> to_ip('192.168.32.106')
    '\xc0\xa8 j'

    """
    try:
        return socket.inet_aton(ip_string)
    except OSError:
        raise ValueError("'%s' is not a valid dotted quad IPv4 address")


def from_ip(packed_ip):
    """Takes a 4-bytes string representation of an IP and return the human-readable
    representation as a unicode string.

    >>> from_ip(b'\xff\xff\xff\xff')
    '255.255.255.255'
    >>> from_ip(b'\xc0\xa8 j')
    '192.168.32.106'

    """
    try:
        return socket.inet_ntoa(packed_ip)
    except OSError:
        raise ValueError("'%s' is not a valid packed IPv4 address")


def norm_ip(ip_string):
    """Return a normalized representation of an IPv4 address string, which
    is the dotted quad notation.

    Raise a ValueError if the IPv4 address is invalid.

    """
    return from_ip(to_ip(ip_string))


def is_normed_ip(ip_string):
    """Return true if the given IP address string is in normalized format,
    else false.

    """
    try:
        digits = list(map(int, ip_string.split('.')))
    except ValueError:
        # probably a non integer in the string
        return False
    else:
        if len(digits) != 4:
            return False
        else:
            return all(0 <= n <= 255 for n in digits)


def to_mac(mac_string: str) -> str:
    """Takes a human-readable MAC address unicode string (i.e.
    '00:1a:2b:33:44:55') and return a 6-bytes string representation of it.

    Here's some accepted value:
    - 00:1a:2b:3c:4d:5e
    - 00-1a-2b-3c-4d-5e
    - 00:1A:2B:3C:4D:5E
    - 00:1A:2B:3C:4d:5e
    - 001a2b3c4d5e
    - 001A2B3C4D5E
    - 00:A:2B:C:d:5e

    >>> to_mac(u'ff:ff:ff:ff:ff:ff')
    '\xff\xff\xff\xff\xff\xff'

    """
    if not (match := _MAC_ADDR.match(mac_string)):
        raise ValueError('invalid MAC string')

    if not (sep := match.group(1)):
        # no separator - length must be equal to 12 in this case
        if len(mac_string) != 12:
            raise ValueError('invalid MAC string')
        return ''.join(chr(int(mac_string[i : i + 2], 16)) for i in range(0, 12, 2))

    tokens = mac_string.split(sep)
    return ''.join(chr(int(token, 16)) for token in tokens)


def from_mac(packed_mac: str, separator: str = ':', uppercase: bool = False) -> str:
    """Takes a 6-bytes string representation of a MAC address and return the
    human-readable representation.

    >>> from_mac('\xff\xff\xff\xff\xff\xff', ':', False)
    'ff:ff:ff:ff:ff:ff'

    """
    if len(packed_mac) != 6:
        raise ValueError('invalid packed MAC')
    if uppercase:
        fmt = '%02X'
    else:
        fmt = '%02x'
    return separator.join(fmt % ord(e) for e in packed_mac)


def norm_mac(mac_string: str) -> str:
    """Return a lowercase, separated by colon, representation of a MAC
    address string.

    Raise a ValueError if the MAC address is invalid.

    >>> norm_mac('0011223344aa')
    '00:11:22:33:44:aa'
    >>> norm_mac('0011223344AA')
    '00:11:22:33:44:aa'
    >>> norm_mac('00-11-22-33-44-AA')
    '00:11:22:33:44:aa'
    >>> norm_mac('00:11:22:33:44:aa')
    '00:11:22:33:44:aa'

    """
    return from_mac(to_mac(mac_string))


def is_normed_mac(mac_string: str) -> bool:
    """Return true if the given MAC address string is in normalized format,
    else false.

    """
    return bool(_NORMED_MAC.match(mac_string))


def format_mac(mac_string: str, separator: str = ':', uppercase: bool = False):
    """Return a freely formatted representation of a MAC address string."""
    return from_mac(to_mac(mac_string), separator, uppercase)


def norm_uuid(uuid_string: str) -> str:
    """Return a lowercase, separated by hyphen, representation of a UUID
    string.

    Raise a ValueError if the UUID is invalid.

    >>> norm_uuid('550E8400-E29B-41D4-A716-446655440000')
    '550e8400-e29b-41d4-a716-446655440000'

    """
    lower_uuid_string = uuid_string.lower()
    if is_normed_uuid(lower_uuid_string):
        return lower_uuid_string
    raise ValueError(f'invalid uuid: {uuid_string}')


def is_normed_uuid(uuid_string: str) -> bool:
    """Return true if the given UUID string is in normalized format, else
    false.

    >>> is_normed_uuid('550e8400-e29b-41d4-a716-446655440000')
    True
    >>> is_normed_uuid('foo')
    False

    """
    return bool(_NORMED_UUID.match(uuid_string))


if __name__ == '__main__':
    import doctest

    doctest.testmod(verbose=True)
