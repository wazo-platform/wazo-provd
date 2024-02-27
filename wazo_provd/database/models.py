# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import abc
import dataclasses
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Model(metaclass=abc.ABCMeta):
    _meta: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        self_dict = dataclasses.asdict(self)
        del self_dict['_meta']
        return self_dict


@dataclasses.dataclass
class Tenant(Model):
    uuid: UUID
    provisioning_key: str

    _meta = {'primary_key': 'uuid'}
