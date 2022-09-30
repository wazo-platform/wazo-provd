# Copyright 2011-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Automatic plugin association."""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from enum import IntEnum
from operator import itemgetter
from typing import Any

from provd.devices.ident import AbstractDeviceUpdater
from twisted.internet import defer

logger = logging.getLogger(__name__)


class DeviceSupport(IntEnum):
    # Used when the device is known to not be supported
    NONE = 0
    # Used when it is expected the device won't be supported
    IMPROBABLE = 100
    # Used when not enough information is available to take a decision or when
    # the plugin is not interested in supporting the device.
    UNKNOWN = 200
    # Used when it is expected the device will be supported, but we are either
    # missing some information, either we don't know for real if this device is
    # supported, i.e. no test have been done
    PROBABLE = 300
    # The device is supported, but in an incomplete way. This might be because
    # it's a kind of device that share some similarities but also have some
    # difference, or because this would be a completely supported device but we
    # did not add explicit support for it
    INCOMPLETE = 400
    # The device is completely supported, i.e. we know it works well, but the
    # device might not be in the version we are targeting, but in a version that
    # is so closely similar that it makes no difference
    COMPLETE = 500
    # The device is exactly what the plugin is targeting.
    EXACT = 600


class AbstractPluginAssociator(metaclass=ABCMeta):

    @abstractmethod
    def associate(self, dev_info: dict[str, Any]) -> DeviceSupport:
        """Return a 'support score' from a device info object."""


class BasePgAssociator(AbstractPluginAssociator):
    def associate(self, dev_info):
        vendor = dev_info.get('vendor')
        if vendor is None:
            return DeviceSupport.UNKNOWN
        model = dev_info.get('model')
        version = dev_info.get('version')
        return self._do_associate(vendor, model, version)

    def _do_associate(self, vendor: str, model: str, version: str) -> DeviceSupport:
        """
        Pre: vendor is not None
        """
        raise NotImplementedError('must be overridden in derived class')


class AbstractConflictSolver(metaclass=ABCMeta):
    @abstractmethod
    def solve(self, pg_ids: list[str]) -> str | None:
        """
        Return a pg_id or None if not able to solve the conflict.

        Pre: len(pg_ids) > 1
        """


class ReverseAlphabeticConflictSolver(AbstractConflictSolver):
    def solve(self, pg_ids):
        return max(pg_ids)


class PluginAssociatorDeviceUpdater(AbstractDeviceUpdater):
    force_update = False
    min_level = DeviceSupport.PROBABLE

    def __init__(self, pg_mgr, conflict_solver):
        self._pg_mgr = pg_mgr
        self._solver = conflict_solver

    def update(self, dev, dev_info, request, request_type):
        if self.force_update or 'plugin' not in dev:
            pg_id = self._do_update(dev_info)
            if pg_id:
                dev['plugin'] = pg_id
        return defer.succeed(False)

    def _do_update(self, dev_info):
        pg_scores = self._get_scores(dev_info)
        if pg_scores:
            max_score, pg_ids = max(pg_scores.items(), key=itemgetter(0))
            if max_score >= self.min_level:
                assert pg_ids
                if len(pg_ids) == 1:
                    return pg_ids[0]
                else:
                    pg_id = self._solver.solve(pg_ids)
                    if pg_id:
                        return pg_id
                    else:
                        logger.warning('Conflict resolution yielded nothing for plugins: %s',
                                       pg_ids)
        return None

    def _get_scores(self, dev_info):
        pg_scores = defaultdict(list)
        for pg_id, pg in self._pg_mgr.items():
            sstor = pg.pg_associator
            if sstor is not None:
                try:
                    score = sstor.associate(dev_info)
                    logger.debug('Associator: %s = score %s', pg_id, score)
                except Exception:
                    logger.error('Error during plugin association for plugin %s',
                                 pg_id, exc_info=True)
                else:
                    pg_scores[score].append(pg_id)
        return pg_scores
