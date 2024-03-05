# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import abc
import dataclasses
import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Model(metaclass=abc.ABCMeta):
    _meta: ClassVar[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        self_dict = dataclasses.asdict(self)
        return self_dict


@dataclasses.dataclass
class Tenant(Model):
    uuid: UUID
    provisioning_key: str | None = dataclasses.field(default=None)

    _meta = {'primary_key': 'uuid'}


@dataclasses.dataclass
class ServiceConfiguration(Model):
    uuid: UUID
    plugin_server: str | None
    http_proxy: str | None
    https_proxy: str | None
    ftp_proxy: str | None
    locale: str | None
    nat_enabled: bool | None = dataclasses.field(default=False)

    _meta = {'primary_key': 'uuid'}
