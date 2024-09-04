# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from xivo.status import StatusAggregator

_STATUS_AGGREGATOR: StatusAggregator = StatusAggregator()


def get_status_aggregator():
    global _STATUS_AGGREGATOR
    return _STATUS_AGGREGATOR
