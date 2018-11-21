# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that, is_
from wazo_provd_client import operation


def operation_successful(tested, location):
    operation_progress = tested.get_operation(location)
    assert_that(operation_progress.state, is_(operation.OIP_SUCCESS))
