# Copyright 2011-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Callable

import binascii
import uuid


def numeric_id_generator(prefix='', start=0):
    n = start
    while True:
        yield f"{prefix}{n}"
        n += 1


def uuid_id_generator():
    while True:
        yield str(uuid.uuid4().hex)


def urandom_id_generator(length=12):
    while True:
        with open('/dev/urandom') as f:
            yield str(binascii.hexlify(f.read(length).encode('utf8')))


default_id_generator = uuid_id_generator


def get_id_generator_factory(generator_name: str) -> Callable:
    """Return an ID generator factory from a generator name, or raise
    ValueError if the name is unknown.
    
    Currently accepted generator name are: default, numeric, uuid and
    urandom.
    
    """
    try:
        return globals()[f'{generator_name}_id_generator']
    except KeyError:
        raise ValueError('unknown generator name "%s"' % generator_name)
