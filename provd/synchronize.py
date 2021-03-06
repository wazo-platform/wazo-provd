# -*- coding: utf-8 -*-
# Copyright 2011-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Synchronization services for devices."""


import logging
from twisted.internet import defer, threads
from wazo_amid_client import Client as AmidClient

logger = logging.getLogger(__name__)

_SYNC_SERVICE = None
_AMID_client = None


def get_AMID_client(**config):
    global _AMID_client
    if not _AMID_client:
        _AMID_client = AmidClient(**config)
    return _AMID_client


class AMIError(Exception):
    pass


class AsteriskAMISynchronizeService(object):

    TYPE = 'AsteriskAMI'

    def __init__(self, amid_client):
        self._amid = amid_client

    def _sip_notify(self, destination, event, extra_vars=None):
        logger.debug('Notify %s, event %s, extra_vars: %s', destination, event, extra_vars)
        extra_vars = extra_vars or []
        variables = ['Event={}'.format(event)]
        if extra_vars:
            variables.extend(extra_vars)

        params = {'Variable': variables}
        params.update(destination)

        self._amid.action('PJSIPNotify', params)

    def sip_notify_by_ip(self, ip, event, extra_vars=None):
        destination = {'URI': 'sip:anonymous@{}'.format(ip)}
        self._sip_notify(destination, event, extra_vars)

    def sip_notify_by_peer(self, peer, event, extra_vars=None):
        destination = {'Endpoint': peer}
        self._sip_notify(destination, event, extra_vars)

    # backward compatibility with older plugins
    sip_notify = sip_notify_by_ip


def register_sync_service(sync_service):
    """Register a synchronize service globally."""
    logger.info('Registering synchronize service: %s', sync_service)
    global _SYNC_SERVICE
    _SYNC_SERVICE = sync_service


def unregister_sync_service():
    """Unregister the global synchronize service.

    This is a no-op if there was no register service registered.

    If a synchronize service was registered, this function will
    call its close method.

    """
    global _SYNC_SERVICE
    if _SYNC_SERVICE is not None:
        logger.info('Unregistering synchronize service: %s', _SYNC_SERVICE)
        _SYNC_SERVICE = None
    else:
        logger.info('No synchronize service registered')


def get_sync_service():
    """Return the globally registered synchronize service or None if no
    synchronize service has been registered.

    """
    return _SYNC_SERVICE


class SynchronizeException(Exception):
    pass


def standard_sip_synchronize(device, event='check-sync', extra_vars=None):
    sync_service = _SYNC_SERVICE
    if sync_service is None or sync_service.TYPE != 'AsteriskAMI':
        return defer.fail(SynchronizeException('Incompatible sync service: %s' % sync_service))

    for fun in [_synchronize_by_peer, _synchronize_by_ip]:
        d = fun(device, event, sync_service, extra_vars)
        if d is not None:
            logger.debug('Using synchronize function %s', fun)
            return d

    return defer.fail(SynchronizeException('not enough information to synchronize device'))


def _synchronize_by_peer(device, event, ami_sync_service, extra_vars=None):
    peer = device.get(u'remote_state_sip_username')
    if not peer:
        return

    is_autoprov = peer.startswith('ap') and len(peer) == 10
    # all devices in autoprov have the same peer starting with "ap" use the ip to avoid restarting all phones
    if is_autoprov:
        return None

    return threads.deferToThread(ami_sync_service.sip_notify_by_peer, peer, event, extra_vars)


def _synchronize_by_ip(device, event, ami_sync_service, extra_vars=None):
    ip = device.get(u'ip')
    if not ip:
        return None

    return threads.deferToThread(ami_sync_service.sip_notify_by_ip, ip, event, extra_vars)
