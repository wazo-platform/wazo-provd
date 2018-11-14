# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class WaitStrategy:

    def wait(self, setupd):
        raise NotImplementedError()


class NoWaitStrategy(WaitStrategy):

    def wait(self, provd):
        pass
