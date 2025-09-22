# Copyright 2011-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import binascii
import uuid
from collections.abc import Callable, Generator
from typing import Literal

GeneratorFactory = Callable[..., Generator[str, None, None]]


def numeric_id_generator(
    prefix: str = '', start: int = 0
) -> Generator[str, None, None]:
    n = start
    while True:
        yield f"{prefix}{n}"
        n += 1


def uuid_id_generator() -> Generator[str, None, None]:
    while True:
        yield str(uuid.uuid4().hex)


def urandom_id_generator(length: int = 12) -> Generator[str, None, None]:
    while True:
        with open('/dev/urandom') as f:
            yield str(binascii.hexlify(f.read(length).encode('utf8')))


default_id_generator = uuid_id_generator


def get_id_generator_factory(
    generator_name: Literal['default', 'numeric', 'uuid']
) -> GeneratorFactory:
    """Return an ID generator factory from a generator name, or raise
    ValueError if the name is unknown.

    Currently accepted generator name are: default, numeric, uuid and
    urandom.

    """
    try:
        return globals()[f'{generator_name}_id_generator']
    except KeyError:
        raise ValueError(f'Unknown generator name "{generator_name}"')
