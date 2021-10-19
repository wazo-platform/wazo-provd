# Copyright 2018-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
from twisted.web.static import File


class ResponseFile(File):

    def render(self, request):
        return File.render(self, request)

    def render_OPTIONS(self, request):
        return ''
