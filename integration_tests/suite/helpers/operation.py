# Copyright 2018-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
from hamcrest import assert_that, is_
from wazo_provd_client import operation


def operation_successful(operation_ressource):
    operation_ressource.update()
    assert_that(operation_ressource.state, is_(operation.OIP_SUCCESS))


def operation_fail(operation_ressource):
    operation_ressource.update()
    assert_that(operation_ressource.state, is_(operation.OIP_FAIL))
