# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from twisted.web.static import File


class ResponseFile(File):

    def render(self, request):
        return File.render(self, request)

    def render_OPTIONS(self, request):
        return ''
