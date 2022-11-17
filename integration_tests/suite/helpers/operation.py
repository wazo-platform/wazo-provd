# Copyright 2018-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, is_
from wazo_provd_client import operation


def operation_successful(operation_resource):
    operation_resource.update()
    assert_that(operation_resource.state, is_(operation.OIP_SUCCESS))


def operation_fail(operation_resource):
    operation_resource.update()
    assert_that(operation_resource.state, is_(operation.OIP_FAIL))
