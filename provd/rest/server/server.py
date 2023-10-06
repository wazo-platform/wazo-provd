# Copyright 2011-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Module that defines the REST server for the provisioning server
configuration.

"""


# TODO we sometimes return 400 error when it's not a client error but a server error;
#      that said raised exceptions sometimes does not permit to differentiate...
# XXX passing a 'dhcp_request_processing_service' around doesn't look really
#     good and we might want to create an additional indirection level so that
#     it's a bit cleaner
from __future__ import annotations

import functools
import json
import logging
from binascii import a2b_base64

from provd.app import (
    InvalidIdError,
    DeviceNotInProvdTenantError,
    TenantInvalidForDeviceError,
    NonDeletableError,
)
from provd.localization import get_locale_and_language
from provd.operation import format_oip, operation_in_progres_from_deferred
from provd.persist.common import ID_KEY
from provd.plugins import BasePluginManagerObserver
from provd.rest.util import PROV_MIME_TYPE, uri_append_path
from provd.servers.http_site import AuthResource, Request
from provd.rest.server.util import accept_mime_type, numeric_id_generator
from provd.services import InvalidParameterError
from provd.util import norm_mac, norm_ip, decode_bytes, decode_value
from twisted.web import http
from twisted.web.server import NOT_DONE_YET
from .auth import required_acl
from .auth import get_auth_verifier
from xivo.tenant_helpers import UnauthorizedTenant

logger = logging.getLogger(__name__)

auth_verifier = get_auth_verifier()

REL_INSTALL_SRV = 'srv.install'
REL_INSTALL = 'srv.install.install'
REL_UNINSTALL = 'srv.install.uninstall'
REL_INSTALLED = 'srv.install.installed'
REL_INSTALLABLE = 'srv.install.installable'
REL_UPGRADE = 'srv.install.upgrade'
REL_UPDATE = 'srv.install.update'
REL_CONFIGURE_SRV = 'srv.configure'
REL_CONFIGURE_PARAM = 'srv.configure.param'

_PPRINT = False
if _PPRINT:
    json_dumps = functools.partial(json.dumps, sort_keys=True, indent=4)
else:
    json_dumps = functools.partial(json.dumps, separators=(',', ':'))


def new_id_generator():
    return numeric_id_generator(start=1)


def json_response(data: dict) -> bytes:
    return json_dumps(data).encode('utf-8')


def respond_no_content(request: Request, response_code=http.NO_CONTENT):
    request.setResponseCode(response_code)
    # next lines are tricks for twisted to omit the 'Content-Type' and 'Content-Length'
    # of 'No content' response. This is not strictly necessary per the RFC, but it certainly
    # makes the HTTP response cleaner (but not my source code)
    request.responseHeaders.removeHeader(b'Content-Type')
    request.finish()
    return NOT_DONE_YET


def respond_created_no_content(request: Request, location):
    request.setHeader(b'Location', location.encode('ascii'))
    return respond_no_content(request, http.CREATED)


def respond_error(request: Request, err_msg, response_code=http.BAD_REQUEST):
    request.setResponseCode(response_code)
    request.setHeader(b'Content-Type', b'text/plain; charset=ascii')
    return str(err_msg).encode('ascii')


def respond_bad_json_entity(request: Request, err_msg=None):
    if err_msg is None:
        err_msg = 'Missing information in received entity'
    return respond_error(request, err_msg)


def respond_no_resource(request: Request, response_code=http.NOT_FOUND):
    request.setResponseCode(response_code)
    request.setHeader(b'Content-Type', b'text/plain; charset=ascii')
    return b'No such resource'


def deferred_respond_unauthorized(request: Request):
    request.setResponseCode(http.UNAUTHORIZED)
    request.write(b'Unauthorized')
    request.finish()


def deferred_respond_no_content(request: Request, response_code=http.NO_CONTENT):
    request.setResponseCode(response_code)
    request.responseHeaders.removeHeader(b'Content-Type')
    request.finish()


def deferred_respond_error(request: Request, err_msg, response_code=http.BAD_REQUEST):
    request.setResponseCode(response_code)
    request.setHeader(b'Content-Type', b'text/plain; charset=ascii')
    request.write(str(err_msg).encode('utf8'))
    request.finish()


def deferred_respond_ok(request: Request, data, response_code=http.OK):
    request.setResponseCode(response_code)
    if isinstance(data, str):
        data = data.encode('utf-8')
    request.write(data)
    request.finish()


def deferred_respond_no_resource(request: Request, response_code=http.NOT_FOUND):
    request.setResponseCode(response_code)
    request.setHeader(b'Content-Type', b'text/plain; charset=ascii')
    request.write(b'No such resource')
    request.finish()


def json_response_entity(fun):
    """To use on resource render's method that responds with a PROV_MIME_TYPE
    entity.

    This check that the request is ready to accept such entity, and it will
    set the Content-Type of the response before handling the request to the
    wrapped function. That way, it's still possible for the render function
    to respond with a different content.

    """
    @functools.wraps(fun)
    def aux(self, request: Request):
        if not accept_mime_type(PROV_MIME_TYPE, request):
            return respond_error(
                request,
                f'You must accept the "{PROV_MIME_TYPE}" MIME type.',
                http.NOT_ACCEPTABLE
            )
        request.setHeader(b'Content-Type', PROV_MIME_TYPE.encode('ascii'))
        return fun(self, request)
    return aux


def json_request_entity(fun):
    """To use on resource render's method that receives a PROV_MIME_TYPE
    entity.

    The entity will be deserialized and passed as a third argument to the
    render function.

    """
    @functools.wraps(fun)
    def aux(self, request: Request):
        content_type = decode_bytes(request.getHeader(b'Content-Type'))
        if content_type != PROV_MIME_TYPE:
            return respond_error(
                request,
                f'Entity must be in media type "{PROV_MIME_TYPE}".',
                http.UNSUPPORTED_MEDIA_TYPE
            )
        try:
            content = json.loads(request.content.getvalue())
        except ValueError as e:
            logger.info('Received invalid JSON document: %s', e)
            return respond_error(request, f'Invalid JSON document: {e}'.encode())
        return fun(self, request, content)
    return aux


def _add_selector_parameter(args, result):
    # q={"configured": false}
    result['selector'] = {}
    if 'q64' in args:
        try:
            raw_selector = a2b_base64(args['q64'][0])
        except Exception as e:
            logger.warning('Invalid q64 value: %s', e)
        else:
            try:
                selector = json.loads(raw_selector)
            except ValueError as e:
                logger.warning('Invalid q64 value: %s', e)
            else:
                result['selector'] = selector
    elif 'q' in args:
        raw_selector = args['q'][0]
        try:
            selector = json.loads(raw_selector)
        except ValueError as e:
            logger.warning('Invalid q value: %s', e)
        else:
            result['selector'] = selector


def _add_fields_parameter(args, result):
    # fields=mac,ip
    if 'fields' in args:
        raw_fields = args['fields'][0]
        fields = raw_fields.split(',')
        result['fields'] = fields


def _add_skip_parameter(args, result):
    # skip=10
    if 'skip' in args:
        raw_skip = args['skip'][0]
        try:
            skip = int(raw_skip)
        except ValueError as e:
            logger.warning('Invalid skip value: %s', e)
        else:
            result['skip'] = skip


def _add_limit_parameters(args, result):
    # limit=10
    if 'limit' in args:
        raw_limit = args['limit'][0]
        try:
            limit = int(raw_limit)
        except ValueError as e:
            logger.warning('Invalid limit value: %s', e)
        else:
            result['limit'] = limit


def _add_sort_parameters(args, result):
    # sort=mac
    # sort=mac&sort_ord=ASC
    if 'sort' in args:
        key = args['sort'][0]
        direction = 1
        if 'sort_ord' in args:
            raw_direction = args['sort_ord'][0]
            if raw_direction == 'ASC':
                direction = 1
            elif raw_direction == 'DESC':
                direction = -1
            else:
                logger.warning('Invalid sort_ord value: %s', raw_direction)
        result['sort'] = (key, direction)


def find_arguments_from_request(request: Request) -> dict[str, Any]:
    # Return a dictionary representing the different find parameters that
    # were passed in the request. The dictionary is usable as **kwargs for
    # the find method of collections.
    result = {}
    args = decode_value(request.args)
    _add_selector_parameter(args, result)
    _add_fields_parameter(args, result)
    _add_skip_parameter(args, result)
    _add_limit_parameters(args, result)
    _add_sort_parameters(args, result)
    return result


def _return_value(value):
    # Return a function that when called will return the value passed in
    # arguments. This can be useful when working with deferred.
    def aux(*args, **kwargs):
        return value
    return aux


_return_none = _return_value(None)


def _ignore_deferred_error(deferred):
    # Ignore any error raise by the deferred by placing an errback that
    # will return None. This is useful if you don't care about the deferred
    # yet you don't want to see an error message in the log when the deferred
    # will be garbage collected.
    deferred.addErrback(_return_none)


class IntermediaryResource(AuthResource):
    # TODO document better and maybe change the name

    def __init__(self, links):
        """
        links -- a list of tuple (rel, path, resource)

        For example:
        links = [('foo', 'foo_sub_uri', server.Data('text/plain', 'foo'),
                 ('bar', 'bar_sub_uri', server.Data('text/plain', 'bar')]
        IntermediaryResource(links)

        The difference between this resource and a plain Resource is that a
        GET request will yield something.

        """
        super().__init__()
        self._links = links
        self._register_children()

    def _register_children(self):
        for _, path, resource in self._links:
            self.putChild(path.encode('ascii'), resource)

    def _build_links(self, base_uri):
        return [
            {'rel': rel, 'href': uri_append_path(base_uri, path)}
            for rel, path, _ in self._links
        ]

    @json_response_entity
    def render_GET(self, request: Request):
        content = {'links': self._build_links(request.path)}
        return json_response(content)


class ServerResource(IntermediaryResource):
    def __init__(self, app, dhcp_request_processing_service):
        links = [
            ('dev', 'dev_mgr', DeviceManagerResource(app, dhcp_request_processing_service)),
            ('cfg', 'cfg_mgr', ConfigManagerResource(app)),
            ('pg', 'pg_mgr', PluginManagerResource(app)),
            ('status', 'status', StatusResource()),
            (REL_CONFIGURE_SRV, 'configure', ConfigureServiceResource(app.configure_service)),
        ]
        super().__init__(links)

    @required_acl('provd.read')
    def render_GET(self, request: Request):
        return IntermediaryResource.render_GET(self, request)


class OperationInProgressResource(AuthResource):
    # Note that render_DELETE might be implemented in classes creating these
    # objects, and not on the class itself
    def __init__(self, oip, on_delete=None):
        """
        oip -- an operation in progress object
        on_delete -- either None or a callable taking no argument
        """
        super().__init__()
        self._oip = oip
        self._on_delete = on_delete

    @required_acl('provd.operation.read')
    @json_response_entity
    def render_GET(self, request: Request):
        return json_response({'status': format_oip(self._oip)})

    @required_acl('provd.operation.delete')
    def render_DELETE(self, request: Request):
        if self._on_delete is not None:
            self._on_delete()
        return respond_no_content(request)


class ConfigureServiceResource(AuthResource):
    def __init__(self, cfg_srv):
        """
        cfg_srv -- an object providing the IConfigureService interface
        """
        super().__init__()
        self._cfg_srv = cfg_srv

    def getChild(self, path, request: Request):
        return ConfigureParameterResource(self._cfg_srv, path)

    def _get_localized_description_list(self):
        locale, lang = get_locale_and_language()
        cfg_srv = self._cfg_srv
        if locale is not None:
            locale_name = f'description_{locale}'
            try:
                return getattr(cfg_srv, locale_name)
            except AttributeError:
                if lang != locale:
                    lang_name = f'description_{lang}'
                    try:
                        return getattr(cfg_srv, lang_name)
                    except AttributeError:
                        pass
        # in last case, return the non-localized description
        return cfg_srv.description

    @required_acl('provd.configure.read')
    @json_response_entity
    def render_GET(self, request: Request):
        description_list = self._get_localized_description_list()
        params = []
        for key, description in description_list:
            value = self._cfg_srv.get(key)
            href = uri_append_path(request.path, key)
            params.append({
                'id': key,
                'description': description,
                'value': value,
                'links': [{'rel': REL_CONFIGURE_PARAM, 'href': href}]
            })
        return json_response({'params': params})


class PluginConfigureServiceResource(ConfigureServiceResource):
    def __init__(self, cfg_srv, plugin_id):
        super().__init__(cfg_srv)
        self.plugin_id = plugin_id

    @required_acl('provd.pg_mgr.plugins.{plugin_id}.configure.read')
    @json_response_entity
    def render_GET(self, request: Request):
        return ConfigureServiceResource.render_GET(self, request)


class ConfigureParameterResource(AuthResource):
    def __init__(self, cfg_srv, key):
        super().__init__()
        # key is not necessary to be valid
        self._cfg_srv = cfg_srv
        self.param_id = decode_bytes(key)

    @required_acl('provd.configure.{param_id}.read')
    @json_response_entity
    def render_GET(self, request: Request):
        try:
            value = self._cfg_srv.get(self.param_id)
        except KeyError:
            logger.info('Invalid/unknown key: %s', self.param_id)
            return respond_no_resource(request)
        return json_response({'param': {'value': value}})

    @required_acl('provd.configure.{param_id}.update')
    @json_request_entity
    def render_PUT(self, request: Request, content):
        try:
            value = content['param']['value']
        except KeyError:
            return respond_error(request, 'Wrong information in entity')

        try:
            self._cfg_srv.set(self.param_id, value)
        except InvalidParameterError as e:
            logger.info('Invalid value for key %s: %r', self.param_id, value)
            return respond_error(request, e)
        except KeyError:
            logger.info('Invalid/unknown key: %s', self.param_id)
            return respond_no_resource(request)
        return respond_no_content(request)


class PluginInstallServiceResource(IntermediaryResource):
    def __init__(self, install_srv, plugin_id: str):
        self.plugin_id = decode_bytes(plugin_id)
        links = [
            (REL_INSTALL, 'install', PackageInstallResource(install_srv, plugin_id)),
            (REL_UNINSTALL, 'uninstall', PackageUninstallResource(install_srv, plugin_id)),
            (REL_INSTALLED, 'installed', PackageInstalledResource(install_srv, plugin_id)),
            (REL_INSTALLABLE, 'installable', PackageInstallableResource(install_srv, plugin_id)),
        ]
        super().__init__(links)

    @required_acl('provd.pg_mgr.plugins.{plugin_id}.install.read')
    def render_GET(self, request):
        return IntermediaryResource.render_GET(self, request)


class _OipInstallResource(AuthResource):
    def __init__(self):
        super().__init__()
        self._id_gen = new_id_generator()

    def _add_new_oip(self, oip, request: Request):
        # add a new child to this resource, and return the location
        # of the child
        path = next(self._id_gen)

        def on_delete():
            try:
                del self.children[path.encode('ascii')]
            except KeyError:
                logger.warning('ID "%s" has already been removed', path)
        op_in_progress_res = OperationInProgressResource(oip, on_delete)
        self.putChild(path.encode('ascii'), op_in_progress_res)
        return uri_append_path(request.path, path)


class InstallResource(_OipInstallResource):
    def __init__(self, install_srv):
        super().__init__()
        self._install_srv = install_srv

    def render_POST(self, request: Request, content):
        try:
            pkg_id = content['id']
        except KeyError:
            return respond_bad_json_entity(request, 'Missing "id" key')
        else:
            try:
                deferred, oip = self._install_srv.install(pkg_id)
            except Exception as e:
                # XXX should handle the exception differently if it was
                #     because there's already an installation in progress
                return respond_error(request, e)
            else:
                _ignore_deferred_error(deferred)
                location = self._add_new_oip(oip, request)
                return respond_created_no_content(request, location)


class PluginInstallResource(InstallResource):
    @json_request_entity
    @required_acl('provd.pg_mgr.install.install.create')
    def render_POST(self, request: Request, content):
        return InstallResource.render_POST(self, request, content)


class PackageInstallResource(InstallResource):
    def __init__(self, install_srv, plugin_id):
        super().__init__(install_srv)
        self.plugin_id = decode_bytes(plugin_id)

    @json_request_entity
    @required_acl('provd.pg_mgr.plugins.{plugin_id}.install.install.create')
    def render_POST(self, request: Request, content):
        return InstallResource.render_POST(self, request, content)


class PackageUninstallResource(AuthResource):
    def __init__(self, install_srv, plugin_id):
        super().__init__()
        self._install_srv = install_srv
        self.plugin_id = plugin_id

    @json_request_entity
    @required_acl('provd.pg_mgr.plugins.{plugin_id}.install.uninstall.create')
    def render_POST(self, request: Request, content):
        try:
            pkg_id = content['id']
        except KeyError:
            return respond_bad_json_entity(request, 'Missing "id" key')
        else:
            try:
                self._install_srv.uninstall(pkg_id)
            except Exception as e:
                return respond_error(request, e)
            else:
                return respond_no_content(request)


class PluginUpgradeResource(_OipInstallResource):
    def __init__(self, install_srv):
        super().__init__()
        self._install_srv = install_srv

    @json_request_entity
    @required_acl('provd.pg_mgr.install.upgrade.create')
    def render_POST(self, request: Request, content):
        try:
            pkg_id = content['id']
        except KeyError:
            return respond_bad_json_entity(request, 'Missing "id" key')
        else:
            try:
                deferred, oip = self._install_srv.upgrade(pkg_id)
            except Exception as e:
                # XXX should handle the exception differently if it was
                #     because there's already an upgrade in progress
                return respond_error(request, e)
            else:
                _ignore_deferred_error(deferred)
                location = self._add_new_oip(oip, request)
                return respond_created_no_content(request, location)


class UpdateResource(_OipInstallResource):
    def __init__(self, install_srv):
        super().__init__()
        self._install_srv = install_srv

    @json_request_entity
    @required_acl('provd.pg_mgr.install.update.create')
    def render_POST(self, request: Request, content):
        try:
            deferred, oip = self._install_srv.update()
        except Exception as e:
            # XXX should handle the exception differently if it was
            #     because there's already an update in progress
            logger.error('Error while updating packages', exc_info=True)
            return respond_error(request, e, http.INTERNAL_SERVER_ERROR)
        else:
            _ignore_deferred_error(deferred)
            location = self._add_new_oip(oip, request)
            return respond_created_no_content(request, location)


class _ListInstallxxxxResource(AuthResource):
    def __init__(self, install_srv, method_name):
        super().__init__()
        self._install_srv = install_srv
        self._method_name = method_name

    @json_response_entity
    def render_GET(self, request: Request):
        fun = getattr(self._install_srv, self._method_name)
        try:
            pkgs = fun()
        except Exception as e:
            logger.error('Error while listing install packages', exc_info=True)
            return respond_error(request, e, http.INTERNAL_SERVER_ERROR)

        return json_response({'pkgs': pkgs})


class InstalledResource(_ListInstallxxxxResource):
    def __init__(self, install_srv):
        super().__init__(install_srv, 'list_installed')

    def render_GET(self, request: Request):
        logger.info('list installed')
        return _ListInstallxxxxResource.render_GET(self, request)


class PluginInstalledResource(InstalledResource):
    @required_acl('provd.pg_mgr.install.installed.read')
    def render_GET(self, request: Request):
        return InstalledResource.render_GET(self, request)


class PackageInstalledResource(InstalledResource):
    def __init__(self, install_srv, plugin_id):
        super().__init__(install_srv)
        self.plugin_id = plugin_id

    @required_acl('provd.pg_mgr.plugins.{plugin_id}.install.installed.read')
    def render_GET(self, request: Request):
        return InstalledResource.render_GET(self, request)


class InstallableResource(_ListInstallxxxxResource):
    def __init__(self, install_srv):
        super().__init__(install_srv, 'list_installable')

    def render_GET(self, request: Request):
        return _ListInstallxxxxResource.render_GET(self, request)


class PluginInstallableResource(InstallableResource):
    @required_acl('provd.pg_mgr.install.installable.read')
    def render_GET(self, request: Request):
        return InstallableResource.render_GET(self, request)


class PackageInstallableResource(InstallableResource):
    def __init__(self, install_srv, plugin_id):
        self.plugin_id = plugin_id
        super().__init__(install_srv)

    @required_acl('provd.pg_mgr.plugins.{plugin_id}.install.installable.read')
    def render_GET(self, request: Request):
        return InstallableResource.render_GET(self, request)


class DeviceManagerResource(IntermediaryResource):
    def __init__(self, app, dhcp_request_processing_service):
        links = [
            ('dev.synchronize', 'synchronize', DeviceSynchronizeResource(app)),
            ('dev.reconfigure', 'reconfigure', DeviceReconfigureResource(app)),
            ('dev.dhcpinfo', 'dhcpinfo', DeviceDHCPInfoResource(app, dhcp_request_processing_service)),
            ('dev.devices', 'devices', DevicesResource(app)),
        ]
        super().__init__(links)

    @required_acl('provd.dev_mgr.read')
    def render_GET(self, request: Request):
        return IntermediaryResource.render_GET(self, request)


class DeviceSynchronizeResource(_OipInstallResource):
    def __init__(self, app):
        super().__init__()
        self._app = app

    @json_request_entity
    @required_acl('provd.dev_mgr.synchronize.create')
    def render_POST(self, request: Request, content):
        try:
            device_id = content['id']
        except KeyError:
            return respond_bad_json_entity(request, 'Missing "id" key')
        else:
            def on_valid_tenant(tenant_uuid):
                return self._is_tenant_valid_for_device(self._app, device_id, tenant_uuid)

            def on_tenant_valid_for_device(tenant_uuid):
                deferred = self._app.dev_synchronize(device_id)
                oip = operation_in_progres_from_deferred(deferred)
                _ignore_deferred_error(deferred)
                location = self._add_new_oip(oip, request)
                return respond_created_no_content(request, location)

            def on_errback(failure):
                if failure.check(InvalidIdError, TenantInvalidForDeviceError, UnauthorizedTenant):
                    deferred_respond_no_resource(request)
                else:
                    deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)

            d = self._verify_tenant(request)
            d.addCallback(on_valid_tenant)
            d.addCallback(on_tenant_valid_for_device)
            d.addErrback(on_errback)
            return NOT_DONE_YET


class DeviceReconfigureResource(AuthResource):
    def __init__(self, app):
        super().__init__()
        self._app = app

    @json_request_entity
    @required_acl('provd.dev_mgr.reconfigure.create')
    def render_POST(self, request: Request, content):
        try:
            device_id = content['id']
        except KeyError:
            return respond_bad_json_entity(request, 'Missing "id" key')
        else:
            def on_valid_tenant(tenant_uuid):
                return self._is_tenant_valid_for_device(self._app, device_id, tenant_uuid)

            def on_tenant_valid_for_device(tenant_uuid):
                return self._app.dev_reconfigure(device_id)

            def on_callback(ign):
                deferred_respond_no_content(request)

            def on_errback(failure):
                deferred_respond_error(request, failure.value)

            d = self._verify_tenant(request)
            d.addCallbacks(on_valid_tenant)
            d.addCallback(on_tenant_valid_for_device)
            d.addCallbacks(on_callback, on_errback)
            return NOT_DONE_YET


class DeviceDHCPInfoResource(AuthResource):
    """Resource for pushing DHCP information into the provisioning server."""
    def __init__(self, app, dhcp_request_processing_service):
        super().__init__()
        self._app = app
        self._dhcp_req_processing_srv = dhcp_request_processing_service

    def _transform_options(self, raw_options) -> dict[int, str]:
        options = {}
        for raw_option in raw_options:
            code = int(raw_option[:3], 10)
            value = ''.join(
                chr(int(token, 16)) for token in raw_option[3:].split('.')
            )
            options[code] = value
        return options

    @json_request_entity
    @required_acl('provd.dev_mgr.dhcpinfo.create')
    def render_POST(self, request: Request, content):
        mac, options = None, None
        try:
            raw_dhcp_info = content['dhcp_info']
            op = raw_dhcp_info['op']
            ip = norm_ip(raw_dhcp_info['ip'])
            if op == 'commit':
                mac = norm_mac(raw_dhcp_info['mac'])
                options = self._transform_options(raw_dhcp_info['options'])
        except (KeyError, TypeError, ValueError) as e:
            logger.warning('Invalid DHCP info content: %s', e)
            return respond_error(request, e)

        if op == 'commit':
            dhcp_request = {'ip': ip, 'mac': mac, 'options': options}
            self._dhcp_req_processing_srv.handle_dhcp_request(dhcp_request)
            return respond_no_content(request)
        if op == 'expiry' or op == 'release':
            # we are keeping this only for compatibility -- release and
            # expiry event doesn't interest us anymore
            return respond_no_content(request)
        return respond_error(request, 'invalid operation value')


class DevicesResource(AuthResource):

    def __init__(self, app):
        super().__init__()
        self._app = app

    def getChild(self, path: bytes, request: Request):
        return DeviceResource(self._app, path)

    def _extract_recurse(self, request: Request):
        for value in request.args.get(b'recurse', []):
            return value in [b'true', b'True']
        return False

    @json_response_entity
    @required_acl('provd.dev_mgr.devices.read')
    def render_GET(self, request: Request):
        find_arguments = find_arguments_from_request(request)

        def on_callback(devices):
            data = json_dumps({'devices': list(devices)})
            deferred_respond_ok(request, data)

        def on_errback(failure):
            deferred_respond_error(request, failure.value)

        recurse = self._extract_recurse(request)
        tenant_uuids = self._build_tenant_list_from_request(request, recurse=recurse)
        find_arguments['selector']['tenant_uuid'] = {'$in': tenant_uuids}
        d = self._app.dev_find(**find_arguments)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET

    @json_request_entity
    @required_acl('provd.dev_mgr.devices.create')
    def render_POST(self, request: Request, content):
        # XXX praise KeyError
        device = content['device']

        def on_valid_tenant(tenant_uuid):
            device['tenant_uuid'] = tenant_uuid
            logger.debug('Inserting device using tenant_uuid %s', tenant_uuid)
            return self._app.dev_insert(device)

        def on_callback(device_id):
            location = uri_append_path(request.path, device_id)
            request.setHeader(b'Location', location.encode('ascii'))
            data = json_dumps({'id': device_id})
            deferred_respond_ok(request, data, http.CREATED)

        def on_errback(failure):
            if failure.check(UnauthorizedTenant):
                deferred_respond_unauthorized(request)
            else:
                deferred_respond_error(request, failure.value)

        d = self._verify_tenant(request)
        d.addCallback(on_valid_tenant)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET


class DeviceResource(AuthResource):
    def __init__(self, app, device_id):
        super().__init__()
        self._app = app
        self.device_id = decode_bytes(device_id)

    @json_response_entity
    @required_acl('provd.dev_mgr.devices.{device_id}.read')
    def render_GET(self, request: Request):
        def on_callback(device):
            if device is None:
                deferred_respond_no_resource(request)
            else:
                data = json_dumps({'device': device})
                deferred_respond_ok(request, data)

        def on_error(failure):
            deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)

        tenant_uuids = self._build_tenant_list_from_request(request, recurse=True)
        d = self._app.dev_find_one({'id': self.device_id, 'tenant_uuid': {'$in': tenant_uuids}})
        d.addCallbacks(on_callback, on_error)
        return NOT_DONE_YET

    @json_request_entity
    @required_acl('provd.dev_mgr.devices.{device_id}.update')
    def render_PUT(self, request: Request, content):
        # XXX praise KeyError
        device = content['device']
        # XXX praise TypeError if device not dict
        device[ID_KEY] = self.device_id

        def on_valid_tenant(tenant_uuid):
            return self._is_device_in_provd_tenant(self._app, self.device_id, tenant_uuid)

        def on_device_in_provd_tenant(tenant_uuid):
            device['tenant_uuid'] = tenant_uuid
            return self._app.dev_update(device)

        def on_device_not_in_provd_tenant(failure):
            failure.trap(DeviceNotInProvdTenantError)
            tenant_uuid = failure.value.tenant_uuid
            return self._is_tenant_valid_for_device(self._app, self.device_id, tenant_uuid)

        def on_tenant_valid_for_device(tenant_uuid):
            return self._app.dev_update(device)

        def on_callback(_):
            deferred_respond_no_content(request)

        def on_errback(failure):
            if failure.check(InvalidIdError, TenantInvalidForDeviceError, UnauthorizedTenant):
                deferred_respond_no_resource(request)
            else:
                logger.error('Unknown error: %s', failure)
                deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)

        d = self._verify_tenant(request)
        d.addCallback(on_valid_tenant)
        d.addCallbacks(on_device_in_provd_tenant, on_device_not_in_provd_tenant)
        d.addCallbacks(on_tenant_valid_for_device)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET

    @required_acl('provd.dev_mgr.devices.{device_id}.delete')
    def render_DELETE(self, request: Request):
        def on_valid_tenant(tenant_uuid):
            return self._is_tenant_valid_for_device(self._app, self.device_id, tenant_uuid)

        def on_tenant_valid_for_device(tenant_uuid):
            return self._app.dev_delete(self.device_id)

        def on_callback(_):
            deferred_respond_no_content(request)

        def on_errback(failure):
            if failure.check(InvalidIdError, TenantInvalidForDeviceError, UnauthorizedTenant):
                deferred_respond_no_resource(request)
            else:
                deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)

        d = self._verify_tenant(request)
        d.addCallbacks(on_valid_tenant)
        d.addCallbacks(on_tenant_valid_for_device)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET


class ConfigManagerResource(IntermediaryResource):
    def __init__(self, app):
        links = [
            ('cfg.configs', 'configs', ConfigsResource(app)),
            ('cfg.autocreate', 'autocreate', AutocreateConfigResource(app)),
        ]
        super().__init__(links)

    @required_acl('provd.cfg_mgr.read')
    def render_GET(self, request: Request):
        return IntermediaryResource.render_GET(self, request)


class AutocreateConfigResource(AuthResource):
    def __init__(self, app):
        super().__init__()
        self._app = app

    @json_request_entity
    @required_acl('provd.cfg_mgr.autocreate.create')
    def render_POST(self, request: Request, content):
        def on_callback(config_id):
            location = uri_append_path(request.path, config_id)
            request.setHeader(b'Location', location.encode('ascii'))
            data = json_dumps({'id': config_id})
            deferred_respond_ok(request, data, http.CREATED)

        def on_errback(failure):
            deferred_respond_error(request, failure.value)
        d = self._app.cfg_create_new()
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET


class ConfigsResource(AuthResource):
    def __init__(self, app):
        super().__init__()
        self._app = app

    def getChild(self, path: bytes, request: Request):
        return ConfigResource(self._app, path)

    @json_response_entity
    @required_acl('provd.cfg_mgr.configs.read')
    def render_GET(self, request: Request):
        find_arguments = find_arguments_from_request(request)

        def on_callback(configs):
            data = json_dumps({'configs': list(configs)})
            deferred_respond_ok(request, data)

        def on_errback(failure):
            deferred_respond_error(request, failure.value)
        d = self._app.cfg_find(**find_arguments)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET

    @json_request_entity
    @required_acl('provd.cfg_mgr.configs.create')
    def render_POST(self, request: Request, content):
        # XXX praise KeyError
        config = content['config']

        def on_callback(config_id):
            location = uri_append_path(request.path, config_id)
            request.setHeader('Location', location.encode('ascii'))
            data = json_dumps({'id': config_id})
            deferred_respond_ok(request, data, http.CREATED)

        def on_errback(failure):
            deferred_respond_error(request, failure.value)
        d = self._app.cfg_insert(config)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET


class ConfigResource(AuthResource):
    def __init__(self, app, config_id):
        super().__init__()
        self._app = app
        self.config_id = decode_bytes(config_id)

    def getChild(self, path: bytes, request: Request):
        if path == b'raw':
            return RawConfigResource(self._app, self.config_id)
        return super().getChild(path, request)

    @json_response_entity
    @required_acl('provd.cfg_mgr.configs.{config_id}.read')
    def render_GET(self, request: Request):
        def on_callback(config):
            if config is None:
                deferred_respond_no_resource(request)
            else:
                data = json_dumps({'config': config})
                deferred_respond_ok(request, data)

        def on_error(failure):
            deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)

        d = self._app.cfg_retrieve(self.config_id)
        d.addCallbacks(on_callback, on_error)
        return NOT_DONE_YET

    @json_request_entity
    @required_acl('provd.cfg_mgr.configs.{config_id}.update')
    def render_PUT(self, request: Request, content):
        # XXX praise KeyError
        config = content['config']
        # XXX raise TypeError if config not dict ?
        config[ID_KEY] = self.config_id

        def on_callback(_):
            deferred_respond_no_content(request)

        def on_errback(failure):
            if failure.check(InvalidIdError, UnauthorizedTenant):
                deferred_respond_no_resource(request)
            else:
                deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)
        d = self._app.cfg_update(config)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET

    @required_acl('provd.cfg_mgr.configs.{config_id}.delete')
    def render_DELETE(self, request: Request):
        def on_callback(_):
            deferred_respond_no_content(request)

        def on_errback(failure):
            if failure.check(InvalidIdError, UnauthorizedTenant):
                deferred_respond_no_resource(request)
            elif failure.check(NonDeletableError):
                deferred_respond_error(request, failure.value, http.FORBIDDEN)
            else:
                deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)
        d = self._app.cfg_delete(self.config_id)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET


class RawConfigResource(AuthResource):
    def __init__(self, app, config_id):
        super().__init__()
        self._app = app
        self.config_id = decode_bytes(config_id)

    @json_response_entity
    @required_acl('provd.cfg_mgr.configs.{config_id}.raw.read')
    def render_GET(self, request: Request):
        def on_callback(raw_config):
            if raw_config is None:
                deferred_respond_no_resource(request)
            else:
                data = json_dumps({'raw_config': raw_config})
                deferred_respond_ok(request, data)

        def on_errback(failure):
            deferred_respond_error(request, failure.value, http.INTERNAL_SERVER_ERROR)
            return failure

        d = self._app.cfg_retrieve_raw_config(self.config_id)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET


class PluginManagerResource(IntermediaryResource):
    def __init__(self, app):
        links = [
            (REL_INSTALL_SRV, 'install', PluginManagerInstallServiceResource(app)),
            ('pg.plugins', 'plugins', PluginsResource(app.pg_mgr)),
            ('pg.reload', 'reload', PluginReloadResource(app)),
        ]
        super().__init__(links)

    @required_acl('provd.pg_mgr.read')
    def render_GET(self, request: Request):
        return IntermediaryResource.render_GET(self, request)


class PluginManagerInstallServiceResource(IntermediaryResource):
    def __init__(self, app):
        install_srv = _PluginManagerInstallServiceAdapter(app)
        pg_mgr_uninstall_res = PluginManagerUninstallResource(app)
        links = [
            (REL_INSTALL, 'install', PluginInstallResource(install_srv)),
            (REL_UNINSTALL, 'uninstall', pg_mgr_uninstall_res),
            (REL_INSTALLED, 'installed', PluginInstalledResource(install_srv)),
            (REL_INSTALLABLE, 'installable', PluginInstallableResource(install_srv)),
            (REL_UPGRADE, 'upgrade', PluginUpgradeResource(install_srv)),
            (REL_UPDATE, 'update', UpdateResource(install_srv)),
        ]
        super().__init__(links)

    @required_acl('provd.pg_mgr.install.read')
    def render_GET(self, request: Request):
        return IntermediaryResource.render_GET(self, request)


class _PluginManagerInstallServiceAdapter:
    # Adapt every method of the IService except uninstall
    def __init__(self, app):
        self._app = app

    def install(self, pkg_id: str):
        return self._app.pg_install(pkg_id)

    def upgrade(self, pkg_id: str):
        return self._app.pg_upgrade(pkg_id)

    @staticmethod
    def _clean_info(pkg_info: dict[str, Any]):
        return {k: v for k, v in pkg_info.items() if k != 'filename'}

    @classmethod
    def _clean_installable_pkgs(cls, pkg_info):
        return {k: cls._clean_info(v) for k, v in pkg_info.items()}

    def list_installable(self):
        return self._clean_installable_pkgs(self._app.pg_mgr.list_installable())

    def list_installed(self):
        return self._app.pg_mgr.list_installed()

    def update(self):
        return self._app.pg_mgr.update()


class PluginManagerUninstallResource(AuthResource):
    def __init__(self, app):
        super().__init__()
        self._app = app

    @json_request_entity
    @required_acl('provd.pg_mgr.install.uninstall.create')
    def render_POST(self, request: Request, content):
        try:
            pkg_id = content['id']
        except KeyError:
            return respond_bad_json_entity(request, 'Missing "id" key')

        def callback(_):
            deferred_respond_no_content(request)

        def errback(failure):
            deferred_respond_error(request, failure.value)

        d = self._app.pg_uninstall(pkg_id)
        d.addCallbacks(callback, errback)
        return NOT_DONE_YET


class PluginsResource(AuthResource):
    def __init__(self, pg_mgr):
        super().__init__()
        self._pg_mgr = pg_mgr
        self._children = {
            pg_id: PluginResource(pg) for
            pg_id, pg in self._pg_mgr.items()
        }
        # observe plugin loading/unloading and keep a reference to the weakly
        # referenced observer
        self._obs = BasePluginManagerObserver(
            self._on_plugin_load, self._on_plugin_unload
        )
        pg_mgr.attach(self._obs)

    def _on_plugin_load(self, pg_id):
        self._children[pg_id] = PluginResource(self._pg_mgr[pg_id])

    def _on_plugin_unload(self, pg_id):
        del self._children[pg_id]

    def getChild(self, path: bytes, request: Request):
        try:
            return self._children[path.decode('ascii')]
        except KeyError:
            return super().getChild(path, request)

    @json_response_entity
    @required_acl('provd.pg_mgr.plugins.read')
    def render_GET(self, request: Request):
        return json_response({
            'plugins': {
                pg_id: {'links': [{'rel': 'pg.plugin', 'href': uri_append_path(request.path, pg_id)}]}
                for pg_id in self._pg_mgr
            }
        })


class PluginReloadResource(AuthResource):
    def __init__(self, app):
        super().__init__()
        self._app = app

    @json_request_entity
    @required_acl('provd.pg_mgr.reload.create')
    def render_POST(self, request: Request, content):
        try:
            plugin_id = content['id']
        except KeyError:
            return respond_bad_json_entity(request, 'Missing "id" key')

        def on_callback(ign):
            deferred_respond_no_content(request)

        def on_errback(failure):
            deferred_respond_error(request, failure.value)

        d = self._app.pg_reload(plugin_id)
        d.addCallbacks(on_callback, on_errback)
        return NOT_DONE_YET


class PluginInfoResource(AuthResource):
    def __init__(self, plugin):
        super().__init__()
        self._plugin = plugin
        self.plugin_id = plugin.id

    @json_response_entity
    @required_acl('provd.pg_mgr.plugins.{plugin_id}.info.read')
    def render_GET(self, request: Request):
        return json_response({'plugin_info': self._plugin.info})


class PluginResource(IntermediaryResource):
    def __init__(self, plugin):
        self.plugin_id = plugin.id
        links = [('pg.info', 'info', PluginInfoResource(plugin))]
        if 'install' in plugin.services:
            install_srv = plugin.services['install']
            links.append((REL_INSTALL_SRV, 'install', PluginInstallServiceResource(install_srv, plugin.id)))
        if 'configure' in plugin.services:
            configure_srv = plugin.services['configure']
            links.append((REL_CONFIGURE_SRV, 'configure', PluginConfigureServiceResource(configure_srv, plugin.id)))
        super().__init__(links)

    @required_acl('provd.pg_mgr.plugins.{plugin_id}.read')
    def render_GET(self, request: Request):
        return IntermediaryResource.render_GET(self, request)


class StatusResource(AuthResource):

    @json_response_entity
    @required_acl('provd.status.read')
    def render_GET(self, request: Request):
        return json_response({'rest_api': 'ok'})


def new_authenticated_server_resource(app, dhcp_request_processing_service):
    """Create and return a new server resource that will be accessible only
    by authenticated users.
    """
    return ServerResource(app, dhcp_request_processing_service)
