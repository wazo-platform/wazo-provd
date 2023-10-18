# Copyright 2011-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Extension to the `fetchfw.download` module so that it's usable in an
asynchronous application.

"""
from __future__ import annotations

from xivo_fetchfw import download
from provd.operation import (
    OperationInProgress,
    OIP_SUCCESS,
    OIP_FAIL,
    OIP_PROGRESS,
)
from twisted.internet import threads, defer


def async_download(remote_file, supp_hooks=None):
    """Download a file asynchronously.

    Return a deferred that will fire with None once the download is completed
    or fire its `errback` if the download failed.

    """
    return threads.deferToThread(remote_file.download, supp_hooks or [])


class OperationInProgressHook(download.DownloadHook):
    def __init__(self, oip):
        self._oip = oip
        self._oip.current = 0

    def start(self):
        self._oip.state = OIP_PROGRESS

    def update(self, arg):
        self._oip.current += len(arg)

    def complete(self):
        self._oip.state = OIP_SUCCESS

    def fail(self, exc_value):
        self._oip.state = OIP_FAIL


def async_download_with_oip(remote_file, supp_hooks=None):
    """Download a file asynchronously.

    Return a tuple (deferred, operation in progress). The deferred will fire
    with None once the download is completed or fire its errback if the
    download failed.

    """
    oip = OperationInProgress(end=remote_file.size)
    oip_hook = OperationInProgressHook(oip)
    deferred = async_download(remote_file, [oip_hook] + (supp_hooks or []))
    return deferred, oip


def async_download_multiseq_with_oip(remote_files):
    """Download multiple files asynchronously,in a sequential way.

    Return a tuple (deferred, operation in progress).

    If one download fails, the other downloads will not be started.

    """
    remote_files = list(remote_files)
    top_oip = OperationInProgress(state=OIP_PROGRESS)
    top_deferred = defer.Deferred()
    cur_file_idx = -1

    def download_next_file():
        nonlocal cur_file_idx
        cur_file_idx += 1
        if cur_file_idx < len(remote_files):
            remote_file = remote_files[cur_file_idx]
            dl_deferred, dl_oip = async_download_with_oip(remote_file)
            top_oip.sub_oips.append(dl_oip)
            dl_deferred.addCallbacks(callback, errback)
        else:
            top_oip.state = OIP_SUCCESS
            top_deferred.callback(None)

    def callback(res):
        # successful download of current file
        download_next_file()

    def errback(err):
        # failed download of current file
        top_oip.state = OIP_FAIL
        top_deferred.errback(err)

    download_next_file()
    return top_deferred, top_oip
