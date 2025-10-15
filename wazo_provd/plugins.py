# Copyright 2010-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import contextlib
import json
import logging
import operator
import os
import shutil
import tarfile
from abc import ABCMeta, abstractmethod
from binascii import a2b_hex
from collections.abc import Callable
from typing import Any, TypedDict
from weakref import WeakKeyDictionary

from jinja2.environment import Environment, Template
from jinja2.exceptions import TemplateNotFound
from twisted.internet import defer, threads
from twisted.internet.defer import Deferred
from xivo_fetchfw.download import (
    DefaultDownloader,
    RemoteFile,
    SHA1Hook,
    new_downloaders_from_handlers,
)
from xivo_fetchfw.package import (
    InstallerController,
    PackageManager,
    UninstallerController,
)
from xivo_fetchfw.storage import (
    DefaultFilterBuilder,
    DefaultInstallablePkgStorage,
    DefaultInstalledPkgStorage,
    DefaultInstallMgrFactoryBuilder,
    DefaultPkgBuilder,
    DefaultRemoteFileBuilder,
)

from provd.abstract_plugin import AbstractPlugin as LegacyImportPlugin
from wazo_provd import phonebook, phoned_users
from wazo_provd.download import OperationInProgressHook, async_download_with_oip
from wazo_provd.loaders import ProvdFileSystemLoader
from wazo_provd.localization import get_locale_and_language
from wazo_provd.operation import (
    OIP_FAIL,
    OIP_PROGRESS,
    OIP_SUCCESS,
    OperationInProgress,
)
from wazo_provd.proxy import DynProxyHandler
from wazo_provd.services import (
    AbstractConfigurationService,
    AbstractInstallationService,
    InvalidParameterError,
)

from .abstract_plugin import AbstractPlugin

logger = logging.getLogger(__name__)


class PluginNotLoadedError(Exception):
    pass


class BasePluginInfo(TypedDict):
    description: str


_PLUGIN_INFO_FILENAME = 'plugin-info'
# plugin information filename in each plugin directory.
_PLUGIN_INFO_KEYS = ['capabilities', 'description', 'version']
_PLUGIN_INFO_INSTALLABLE_KEYS = _PLUGIN_INFO_KEYS + ['dsize', 'filename', 'sha1sum']
_PLUGIN_INFO_INSTALLED_KEYS = _PLUGIN_INFO_KEYS


# Export some name/objects to be used by plugins
add_xivo_phonebook_url = phonebook.add_xivo_phonebook_url
add_xivo_phonebook_url_from_format = phonebook.add_xivo_phonebook_url_from_format

add_wazo_phoned_user_service_url = phoned_users.add_wazo_phoned_user_service_url


def _check_raw_plugin_info(raw_plugin_info, plugin_id, keys):
    # Quick and incomplete check of a raw plugin info object.
    for plugin_info_key in keys:
        if plugin_info_key not in raw_plugin_info:
            raise ValueError(
                f'invalid plugin info: missing {plugin_info_key} key in {plugin_id}'
            )


def _clean_localized_description(raw_plugin_info):
    for key in list(raw_plugin_info):
        if key.startswith('description_'):
            del raw_plugin_info[key]


def _new_localize_fun() -> Callable[[dict[str, Any]], None]:
    # Return a function that receives raw plugin info and localizes it
    locale, lang = get_locale_and_language()
    if locale is None:
        return _clean_localized_description

    locale_name = f'description_{locale}'
    if locale == lang:

        def set_locale_description(raw_plugin_info: dict[str, Any]):
            try:
                raw_plugin_info['description'] = raw_plugin_info[locale_name]
            except KeyError:
                pass
            _clean_localized_description(raw_plugin_info)

        return set_locale_description

    lang_name = f'description_{lang}'

    def set_lang_description(raw_plugin_info: dict[str, Any]):
        try:
            raw_plugin_info['description'] = raw_plugin_info[locale_name]
        except KeyError:
            try:
                raw_plugin_info['description'] = raw_plugin_info[lang_name]
            except KeyError:
                pass
        _clean_localized_description(raw_plugin_info)

    return set_lang_description


class Plugin(AbstractPlugin):
    """Base class and entry point of every plugin.

    Here's some guideline every plugin should follow:

    When you have the choice, you SHOULD configure device to use HTTP instead
    of TFTP. HTTP requests have usually more information that can be used
    to identify device. HTTP is also faster (because of TFTP
    lock-step) and not limited in file size transfer. Since HTTP is based
    on TCP, it also usually play nicer with NAT, and in general, integrates
    better in complex network architecture.

    Keep in mind how new devices will interact with the
    plugin for the first time. For example, even if your plugin configure
    its device to use HTTP instead of TFTP, new device might have been
    configured to use TFTP before. This mean you should offer a TFTP service
    and TFTP identification even if you don't plan to make explicit use of
    it. That said, if your device support protocol selection from the DHCP
    server responses, this becomes less important.

    Similarly, keep in mind that you might interact with devices that are
    in a different version then what your plugin is targeting. Your plugin
    should try to recognize and accept these devices, at least the ones
    that are closely related. The plugin should then upgrade them in the
    targeted version of your plugin.

    Attributes:
    id -- the ID of the plugin. This attribute is set after the plugin
          instantiation time by the plugin manager
    services
    http_dev_info_extractor
    http_service
    tftp_dev_info_extractor
    tftp_service

    Plugin class that are made to be instantiated (i.e. the one doing the
    real job, and not superclass that helps it) must have an attribute
    'IS_PLUGIN' that evaluates to true in a boolean context or it won't be
    loaded. This is necessary to distinguish real plugin class from
    'helper' plugin superclasses.

    At load time, the 'execfile_' name is available in the global namespace
    of the entry file. It can be used to 'import' other files in the same or
    subdirectory of the entry plugin file. This method is similar to
    execfile, except that the working directory is changed to the plugin
    directory.

    """

    id = None

    def __init__(self, app, plugin_dir, gen_cfg, spec_cfg):
        """Create a new plugin instance.

        This method is the first method called in the plugin loading process.

        The application guarantees that there will never be more than 1 'active'
        plugin instance at the same time for a same plugin. An instance is
        active between the time of its creation and the time its close method
        is called.

        app -- the application object
        plugin_dir -- the root directory where the plugin lies
        gen_cfg -- a dictionary with generic configuration key-values
            XXX should specify better
        spec_cfg --  a dictionary with plugin-specific configuration key-values
            XXX should specify better

        """
        self._services = {}
        self._plugin_dir = plugin_dir

    def load(self) -> None:
        """Load the plugin.

        This is the first step in the plugin loading system. This should initialize the plugin.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Close (Unload) the plugin.

        This method is the last method called in the plugin unloading process.

        In normal situation, this method is guaranteed to be the last one
        called in the life-cycle of a plugin instance, and may not be called
        more than once.

        """
        pass

    @property
    def info(self) -> dict[str, Any]:
        """Return a dictionary containing information about this plugin.

        The dictionary MUST contain at least the following keys:
          version -- the version of the plugin
          description -- the description of the plugin
          capabilities -- a dictionary where keys are string in format
            "vendor, model, version" and values are capabilities dictionary.

        Note that the returned dictionary contains unicode strings.

        Raise an Exception if the plugin information is missing or invalid.

        """
        plugin_info_path = os.path.join(self._plugin_dir, _PLUGIN_INFO_FILENAME)
        with open(plugin_info_path) as f:
            raw_plugin_info = json.load(f)
        _check_raw_plugin_info(raw_plugin_info, self.id, _PLUGIN_INFO_INSTALLED_KEYS)
        localize_fun = _new_localize_fun()
        localize_fun(raw_plugin_info)
        return raw_plugin_info

    # Methods for additional plugin services

    @property
    def services(
        self,
    ) -> dict[str, AbstractConfigurationService | AbstractInstallationService]:
        """Return a dictionary where keys are service name and values are
        service object.

        This is used so that plugins can offer additional services in a
        standard way.

        If the service name is 'configure', the associated service object must
        provide the IConfigureService interface.

        If the service name is 'install', the associated service object must
        provide the IInstallService interface.
        """
        return self._services

    @services.setter
    def services(
        self,
        value: dict[str, AbstractConfigurationService | AbstractInstallationService],
    ):
        self._services = value

    # Methods for TFTP/HTTP services

    # Contrary to TFTP and HTTP, there's no DHCP service, but only an extractor
    dhcp_dev_info_extractor = None
    """An object providing the IDeviceInfoExtractor interface for DHCP
    requests or None if there's no such object.

    """

    http_dev_info_extractor = None
    """An object providing the IDeviceInfoExtractor interface for HTTP
    requests or None if there's no such object.

    """

    http_service = None
    """The HTTP service of this plugin, or None if the plugin doesn't offer
    an HTTP service.

    Note that the request objects passed to the render method of this service
    have a 'prov_dev' attribute set to the device object representing the
    device which is doing the request, or None if the device is unknown.

    """

    tftp_dev_info_extractor = None
    """An object providing the IDeviceInfoExtractor interface for TFTP
    request or None if there's no such object.

    """

    tftp_service = None
    """The TFTP service of this plugin, or None if the plugin
    doesn't offer a TFTP service.

    Note that the request objects passed to the handle_read_request method of
    this service have a 'prov_dev' key set to the device object representing
    the device which is doing the request, or None if the device is unknown.

    """

    pg_associator = None
    """Return an object providing the IPluginAssociator interface, or None if
    the plugin doesn't have a plugin associator.

    """

    # Methods for device configuration

    def configure_common(self, raw_config: dict[str, Any]) -> None:
        """Apply a non-device specific configuration to the plugin. In typical
        case, this will configure the 'common files' shared by all the devices.

        This method is called automatically the first time an installed plugin
        is loaded, and also called when there's a change to the common config.
        Note that this method might also be called more often than
        technically needed.

        raw_config is a raw config object with all the common configurations
        parameters. An 'ip', 'http_port' and 'tftp_port' parameters are
        guaranteed to be present. Plugin class can modify this object.

        This method is synchronous/blocking.

        """
        pass

    def configure(self, device: dict[str, str], raw_config: dict[str, Any]) -> None:
        """Configure the plugin so that the raw config is applied to the
        device. This method MUST not synchronize the configuration between
        the phone and the provisioning server. This method is called only to
        synchronize the config between the config manager and the plugin. See
        the synchronize method for more info on the device configuration life cycle.

        This method is called in these cases:
        - a device object with a config associated to it has been assigned
          to this plugin
        - the config object used by a device has been updated
        - one of the mac, ip, vendor, model or version key of a device object
          managed by this plugin has been updated

        This method is mostly useful for 'pull type' plugins, especially static
        pull type plugin. For these plugin, this is the right time to write the
        device specific configuration file to the filesystem. This makes sure
        the config inside the device specific configuration file is in sync
        with the config object from the config manager.

        Pre:  device is a device object (can't be None)
              raw_config is a raw config object (can't be None). The plugin
                is free to modify this object (it won't affect anything).
                The meaning of the value in the config object are defined in
                the config module.
        Post: after a call to this method, if the device does a request for
                its configuration file, its configuration will be as the
                config object

        Plugin class can modify the raw_config object.

        This method is synchronous/blocking.

        """
        pass

    def deconfigure(self, device: dict[str, str]) -> None:
        """De-configure the plugin so that the plugin won't configure the
        device.

        This method is called when:
        - a device is changed from this plugin to another plugin
        - a device is going to be deleted
        - the config has been deleted from a device (i.e. no more 'config' key)

        This method is mostly useful for 'pull type' plugins, especially
        static pull type plugins. This is the right time to delete any device
        specific configuration related to the device. This is to prevent
        unexpected configuration for a device and to keep the plugins
        clean, without out-of-sync cache files in their directories.

        Note that de-configure doesn't mean you should try resetting the
        device to its default value. In fact, you SHOULD NOT do this.

        In some rare circumstances, this method might be called more than
        once for the same device object, so plugin should be prepared to
        such eventuality.

        Pre:  device is a device object
              the method 'configure' has been called at least once with the
                same device object since the last call to de-configure with
                the same device (i.e. a call to de-configure can only follow
                a call to the configure method with the same device, and there
                must not be a call to de-configure between these 2 calls)
        Post: after a call to this method, if device dev does a request for
                its configuration file, it won't be configured with an old
                config (it's ok if the device is configured with the common
                configuration though)

        This method is synchronous/blocking.

        """
        pass

    def synchronize(
        self, device: dict[str, str], raw_config: dict[str, Any]
    ) -> Deferred:
        """Force the device to synchronize its configuration so that it's the
        same as the one in the raw config object.

        Note that an offline device can't be synchronized...

        Pre:  device is a device object (can't be None)
              raw_config is a raw config object (can't be None)
              there has been no change to the config object since the last
                call to the configure method with the same device object and
                config object. Said differently, before this call, there has
                been a call to configure with the same object, and there has
                been no call to de-configure with the same dev object between
                these calls and no other call to configure with the same dev
                object.
        Post: its config has been reloaded

        Plugin class can modify the raw_config object.

        Return a Deferred that fire with None if the resync seems to have
        been successful.

        The deferred will fire its errback with an Exception in the following
        case:
          - re-synchronization is not supported by this plugin.
          - not enough information to resynchronize the device.
          - the resync operation seems to have failed for another reason.
        """
        return defer.fail(Exception("Re-synchronization is not supported"))

    def get_remote_state_trigger_filename(self, device: dict[str, str]) -> str | None:
        """Return the name of the filename for the given device that,
        when the device retrieve this file, implies that the configuration of
        the device is the same as the one in the plugin (i.e. the device
        configuration is in sync with the plugin configuration).

        Return None is there's no such file or if there is not enough information
        in the device to generate the file name.

        Pre: device is a device object, not necessarily configured, because
             the configuration might happen just after.
        """
        return None

    def is_sensitive_filename(self, filename: str) -> bool:
        """Return true if the given filename could point to a file containing
        sensitive information (e.g. SIP username, password), false otherwise.
        """
        return False


class StandardPlugin(Plugin):
    """Abstract base class for plugin classes.

    Although this class doesn't do much at the time of writing this, you'll
    still want to inherit from it, unless you have good reason.

    """

    _TFTPBOOT_DIR = os.path.join('var', 'tftpboot')

    def __init__(self, app, plugin_dir, gen_cfg, spec_cfg):
        super().__init__(app, plugin_dir, gen_cfg, spec_cfg)
        self._tftpboot_dir = os.path.join(plugin_dir, self._TFTPBOOT_DIR)


class TemplatePluginHelper:
    DEFAULT_TPL_DIR = 'templates'
    """Directory where the default templates lies."""
    CUSTOM_TPL_DIR = os.path.join('var', 'templates')
    """Directory where the custom templates lies."""

    def __init__(self, plugin_dir):
        custom_dir = os.path.join(plugin_dir, self.CUSTOM_TPL_DIR)
        default_dir = os.path.join(plugin_dir, self.DEFAULT_TPL_DIR)
        loader = ProvdFileSystemLoader([custom_dir, default_dir])
        self._env = Environment(loader=loader)

    def get_dev_template(self, filename, dev):
        tpl_filenames = []
        if filename:
            tpl_filenames.append(filename + '.tpl')
        if 'model' in dev:
            tpl_filenames.append(dev['model'] + '.tpl')
        tpl_filenames.append('base.tpl')
        return self._get_first_template_from_filenames(tpl_filenames)

    def _get_first_template_from_filenames(self, tpl_filenames):
        tpl_filename = None
        for tpl_filename in tpl_filenames:
            try:
                tpl = self._env.get_template(tpl_filename)
                logger.info('Using template %s', tpl_filename)
                return tpl
            except TemplateNotFound:
                pass
        raise TemplateNotFound(tpl_filename)

    def get_template(self, name: str) -> Template:
        return self._env.get_template(name)

    def dump(self, template, context, filename, encoding='UTF-8', errors='strict'):
        logger.info('Writing template to file "%s"', filename)
        tmp_filename = filename + '.tmp'
        template.stream(context).dump(tmp_filename, encoding, errors)
        os.rename(tmp_filename, filename)

    def render(self, template, context, encoding='UTF-8', errors='replace'):
        return template.render(context).encode(encoding, errors)


class AsyncInstallerController(InstallerController):
    def __init__(self, installable_pkg_sto, installed_pkg_sto, dl_oip, install_oip):
        super().__init__(installable_pkg_sto, installed_pkg_sto)
        self._dl_oip = dl_oip
        self._install_oip = install_oip

    def pre_download(self, remote_files):
        self._dl_oip.state = OIP_PROGRESS

    def download_file(self, remote_file):
        oip = OperationInProgress(end=remote_file.size)
        oip_hook = OperationInProgressHook(oip)
        self._dl_oip.sub_oips.append(oip)
        remote_file.download([oip_hook])

    def post_download(self, remote_files):
        self._dl_oip.state = OIP_SUCCESS

    def pre_install(self, installable_pkgs):
        self._install_oip.state = OIP_PROGRESS

    def post_install(self, installable_pkgs):
        self._install_oip.state = OIP_SUCCESS

    def post_installation(self, exc_value):
        if exc_value is not None:
            if self._dl_oip.state != OIP_SUCCESS:
                self._dl_oip.state = OIP_FAIL
            if self._install_oip.state != OIP_SUCCESS:
                self._install_oip.state = OIP_FAIL


def _new_handlers(proxies=None):
    if proxies is None:
        handlers = []
    else:
        handlers = [DynProxyHandler(proxies)]
    return handlers


class FetchfwPluginHelper(AbstractInstallationService):
    """Helper for plugins that needs to download files to really
    be able to support a certain kind of device.

    """

    PKG_DIR = 'pkgs'
    """Directory where the package definitions are stored."""
    CACHE_DIR = os.path.join('var', 'cache')
    """Directory where the downloaded files are stored/cached."""
    INSTALLED_DIR = os.path.join('var', 'installed')
    """Directory where the 'installed packages DB' is stored."""
    TFTPBOOT_DIR = os.path.join('var', 'tftpboot')
    """Base directory where the files are extracted."""

    @classmethod
    def new_handlers(cls, proxies=None):
        return _new_handlers(proxies)

    @classmethod
    def new_downloaders_from_handlers(cls, handlers=None):
        return new_downloaders_from_handlers(handlers)

    @classmethod
    def new_downloaders(cls, proxies=None):
        handlers = _new_handlers(proxies)
        return new_downloaders_from_handlers(handlers)

    def __init__(self, plugin_dir, downloaders=None, filter_builder=None):
        self._plugin_dir = plugin_dir
        self._in_install_set = set()
        self._pkg_mgr = self._new_pkg_mgr(downloaders, filter_builder)
        self.root_dir = os.path.join(plugin_dir, self.TFTPBOOT_DIR)

    def _new_pkg_mgr(self, downloaders, filter_builder):
        # downloaders and filter_builder can be None
        pkg_db_dir = os.path.join(self._plugin_dir, self.PKG_DIR)
        cache_dir = os.path.join(self._plugin_dir, self.CACHE_DIR)
        installed_db_dir = os.path.join(self._plugin_dir, self.INSTALLED_DIR)

        if downloaders is None:
            downloaders = self.new_downloaders()
        if filter_builder is None:
            filter_builder = DefaultFilterBuilder()
        rfile_builder = DefaultRemoteFileBuilder(cache_dir, downloaders)
        install_mgr_factory_builder = DefaultInstallMgrFactoryBuilder(
            filter_builder, {}
        )
        pkg_builder = DefaultPkgBuilder()
        able_sto = DefaultInstallablePkgStorage(
            pkg_db_dir, rfile_builder, install_mgr_factory_builder, pkg_builder
        )
        ed_sto = DefaultInstalledPkgStorage(installed_db_dir)
        return PackageManager(able_sto, ed_sto)

    def install(self, pkg_id: str):
        """Install a package."""
        logger.info('Installing plugin-package %s', pkg_id)
        if pkg_id in self._in_install_set:
            raise Exception(
                f'an install operation for pkg {pkg_id} is already in progress'
            )
        if pkg_id not in self._pkg_mgr.installable_pkg_sto:
            raise Exception('package not found')

        dl_oip = OperationInProgress('download')
        install_oip = OperationInProgress('install')
        oip = OperationInProgress(
            'install_pkg', OIP_PROGRESS, sub_oips=[dl_oip, install_oip]
        )
        ctrl_factory = AsyncInstallerController.new_factory(dl_oip, install_oip)
        deferred = threads.deferToThread(
            self._pkg_mgr.install, [pkg_id], self.root_dir, ctrl_factory
        )
        self._in_install_set.add(pkg_id)

        def callback(res):
            logger.info('Plugin-package %s installed', pkg_id)
            self._in_install_set.remove(pkg_id)
            oip.state = OIP_SUCCESS
            return res

        def errback(err):
            logger.info(
                'Error while installing plugin-package %s: %s', pkg_id, err.value
            )
            self._in_install_set.remove(pkg_id)
            oip.state = OIP_FAIL
            return err

        deferred.addCallbacks(callback, errback)
        return deferred, oip

    def uninstall(self, pkg_id):
        """Uninstall a package.

        See IInstallService.uninstall.

        """
        logger.info('Uninstalling plugin-package %s', pkg_id)
        ctrl_factory = UninstallerController.new_factory()
        self._pkg_mgr.uninstall([pkg_id], self.root_dir, ctrl_factory)

    def upgrade(self, pkg_id):
        logger.info('Upgrading plugin-package %s', pkg_id)
        self.uninstall(pkg_id)
        return self.install(pkg_id)

    def _new_localize_description_fun(self) -> Callable[[dict[str, Any]], str]:
        locale, lang = get_locale_and_language()
        if locale is None:
            return operator.itemgetter('description')

        locale_name = f'description_{locale}'
        if locale == lang:

            def get_description_by_locale(pkg_info: dict[str, Any]) -> str:
                try:
                    return pkg_info[locale_name]
                except KeyError:
                    return pkg_info['description']

            return get_description_by_locale

        lang_name = f'description_{lang}'

        def get_description_by_language(pkg_info: dict[str, Any]) -> str:
            try:
                return pkg_info[locale_name]
            except KeyError:
                try:
                    return pkg_info[lang_name]
                except KeyError:
                    return pkg_info['description']

        return get_description_by_language

    def list_installable(self):
        """Return a dictionary of installable packages.

        See IInstallService.list_installable.

        """
        localize_desc_fun = self._new_localize_description_fun()
        installable_pkg_sto = self._pkg_mgr.installable_pkg_sto
        return {
            pkg_id: {
                'version': pkg.pkg_info['version'],
                'description': localize_desc_fun(pkg.pkg_info),
                'dsize': sum(rfile.size for rfile in pkg.remote_files),
            }
            for pkg_id, pkg in installable_pkg_sto.items()
        }

    def list_installed(self):
        """Return a dictionary of installed packages.

        See IInstallService.list_installed.

        """
        localize_desc_fun = self._new_localize_description_fun()
        installed_pkg_sto = self._pkg_mgr.installed_pkg_sto
        return {
            pkg_id: {
                'version': pkg.pkg_info['version'],
                'description': localize_desc_fun(pkg.pkg_info),
            }
            for pkg_id, pkg in installed_pkg_sto.items()
        }

    def services(self):
        """Return the following dictionary: {'install': self}."""
        return {'install': self}


class AbstractPluginManagerObserver(metaclass=ABCMeta):
    """Interface that objects which want to be notified of plugin
    loading/unloading MUST provide.

    """

    @abstractmethod
    def pg_load(self, pg_id: str) -> None:
        pass

    @abstractmethod
    def pg_unload(self, pg_id: str) -> None:
        pass


class BasePluginManagerObserver(AbstractPluginManagerObserver):
    # Warning: don't forget to store at least 1 reference to this object
    # after attaching it to the plugin manager since observers are weakly
    # referenced by the plugin manager, so if you do not store any reference,
    # the observer will be automatically garbage collected
    def __init__(self, pg_load=None, pg_unload=None):
        self._pg_load = pg_load
        self._pg_unload = pg_unload

    def pg_load(self, pg_id: str):
        if self._pg_load is not None:
            self._pg_load(pg_id)

    def pg_unload(self, pg_id: str):
        if self._pg_unload is not None:
            self._pg_unload(pg_id)


class PluginManager:
    """Manage the life cycle of plugins in the plugin ecosystem.

    Plugin manager objects have a 'server' attribute which represent the base
    address of the plugin's repository (ex.: http://www.example.com/provd/stable).
    It can be set to None if no server is specified.

    """

    PLUGIN_IFACE_VERSION = 0.2

    _ENTRY_FILENAME = 'entry.py'
    # name of the python plugin code
    _DB_FILENAME = 'plugins.db'
    # plugin definition filename on the remote and local server.

    _INSTALL_LABEL = 'install'
    _DOWNLOAD_LABEL = 'download'
    _UPDATE_LABEL = 'update'

    _observers: WeakKeyDictionary[AbstractPluginManagerObserver, None]

    def __init__(
        self,
        app,
        plugins_dir,
        cache_dir,
        cache_plugin=True,
        check_compat_min=True,
        check_compat_max=True,
    ):
        """
        app -- a provisioning application object
        plugins_dir -- the directory where plugins are installed
        cache_dir -- a directory where plugin-package are downloaded
        cache_plugin -- should we cache the plugin package or not
        """
        self._app = app
        if not os.path.exists(plugins_dir):
            os.mkdir(plugins_dir)
        self._plugins_dir = plugins_dir
        self._cache_dir = cache_dir
        self._cache_plugin = cache_plugin
        self._check_compat_min = check_compat_min
        self._check_compat_max = check_compat_max
        self.server = None
        self._in_update = False
        self._in_install = set()
        self._observers = WeakKeyDictionary()
        self._plugins = {}
        self._downloader = DefaultDownloader(_new_handlers(app.proxies))

    def close(self) -> None:
        """Close the plugin manager.

        This will unload any loaded plugin.

        """
        logger.info('Closing plugin manager...')
        # important not to use an iterator over self._plugins since it is
        # modified in the unload method
        for plugin_id in list(self._plugins):
            self._unload_and_notify(plugin_id)
        logger.info('Plugin manager closed')

    def _db_pathname(self) -> str:
        return os.path.join(self._plugins_dir, self._DB_FILENAME)

    def _join_server_url(self, p: str):
        server = self.server
        if server is None:
            logger.warning('Plugin manager server attribute is not set')
            raise InvalidParameterError("'server' has no value set")
        else:
            if server.endswith('/'):
                return server + p
            return server + '/' + p

    def _extract_plugin(self, cache_filename):
        with contextlib.closing(tarfile.open(cache_filename)) as tfile:
            # XXX this is unsafe unless we have authenticated the tarfile
            tfile.extractall(self._plugins_dir)

    def install(self, plugin_id: str):
        """Install a plugin.

        This does not check if the plugin is already installed and does not
        load the newly installed plugin.

        Return a tuple (deferred, operation in progress).

        Raise an Exception if there's already an installation/upgrade in progress for the plugin.

        Raise an Exception if there's no installable plugin with the specified plugin_id.

        Raise an InvalidParameterError if the plugin package is not in cache
        and no 'server' param has been set.

        """
        logger.info('Installing plugin %s', plugin_id)
        if plugin_id in self._in_install:
            logger.warning(
                'Install operation already in progress for plugin %s', plugin_id
            )
            raise Exception(
                f'an install/upgrade operation for plugin {plugin_id} is already in progress'
            )
        try:
            pg_info = self._get_installable_plugin_info(plugin_id)
        except KeyError:
            logger.error('Can\'t install plugin %s: not found', plugin_id)
            raise
        filename = pg_info['filename']
        cache_filename = os.path.join(self._cache_dir, filename)
        if os.path.isfile(cache_filename):
            try:
                self._extract_plugin(cache_filename)
            except Exception as e:
                top_deferred = defer.fail(e)
                top_oip = OperationInProgress(self._INSTALL_LABEL, OIP_FAIL)
            else:
                top_deferred = defer.succeed(None)
                top_oip = OperationInProgress(self._INSTALL_LABEL, OIP_SUCCESS)
        else:
            url = self._join_server_url(filename)
            rfile = RemoteFile.new_remote_file(
                cache_filename, pg_info['dsize'], url, self._downloader
            )
            sha1hook = SHA1Hook(a2b_hex(pg_info['sha1sum']))
            dl_deferred, dl_oip = async_download_with_oip(rfile, [sha1hook])
            dl_oip.label = self._DOWNLOAD_LABEL
            self._in_install.add(plugin_id)
            top_deferred = defer.Deferred()
            top_oip = OperationInProgress(
                self._INSTALL_LABEL, OIP_PROGRESS, sub_oips=[dl_oip]
            )

            def dl_callback(_):
                self._in_install.remove(plugin_id)
                try:
                    self._extract_plugin(cache_filename)
                except Exception as e:
                    top_oip.state = OIP_FAIL
                    top_deferred.errback(e)
                else:
                    top_oip.state = OIP_SUCCESS
                    top_deferred.callback(None)
                finally:
                    if not self._cache_plugin:
                        os.remove(cache_filename)

            def dl_errback(err):
                self._in_install.remove(plugin_id)
                top_oip.state = OIP_FAIL
                top_deferred.errback(err)

            # do not move this line up (see dl_callback def)
            dl_deferred.addCallbacks(dl_callback, dl_errback)

        def top_callback(res):
            logger.info('Plugin %s installed', plugin_id)
            return res

        def top_errback(err):
            logger.error('Error while installing plugin %s: %s', plugin_id, err.value)
            return err

        top_deferred.addCallbacks(top_callback, top_errback)
        return top_deferred, top_oip

    def upgrade(self, plugin_id):
        """Upgrade a plugin.

        Right now, there is absolutely no difference
        between calling this method and calling the `install` method.

        """
        logger.info('Upgrading plugin %s', plugin_id)
        return self.install(plugin_id)

    def uninstall(self, plugin_id):
        """Uninstall a plugin.

        This does not unload the installed plugin.

        Raise an Exception if there's no installed plugin with the
        specified id.

        """
        logger.info('Uninstalling plugin %s', plugin_id)
        if not self.is_installed(plugin_id):
            logger.error('Can\'t uninstall plugin %s: not installed', plugin_id)
            raise Exception('plugin not found')

        shutil.rmtree(os.path.join(self._plugins_dir, plugin_id))

    def update(self):
        """Download a fresh copy of the plugin definition file from the server.

        Return a tuple (deferred, operation in progress)..

        Raise an Exception if there's already an update operation in progress.

        Raise an InvalidParameterError if no 'server' param has been set,
        or has an invalid value.

        Note:
        - if the downloaded plugin definition file is invalid/corrupted, no
          error will be raised in this method.
        - if the operation fail, for example because of an incomplete
          download, the local copy of the plugin definition file won't be
          changed

        """
        logger.info('Updating plugin definition file')
        if self._in_update:
            logger.warning('Update operation already in progress')
            raise Exception('an update operation is already in progress')

        url = self._join_server_url(self._DB_FILENAME)
        db_pathname = self._db_pathname()
        rfile = RemoteFile.new_remote_file(db_pathname, None, url, self._downloader)
        dl_deferred, dl_oip = async_download_with_oip(rfile)
        dl_oip.label = self._UPDATE_LABEL
        self._in_update = True

        def callback(res):
            logger.info('Plugin definition file updated')
            return res

        def errback(err):
            logger.error('Error while updating plugin definition file: %s', err.value)
            return err

        def dl_end(v):
            self._in_update = False
            return v

        dl_deferred.addCallbacks(callback, errback)
        dl_deferred.addBoth(dl_end)
        return dl_deferred, dl_oip

    def _get_installable_plugin_info(self, plugin_id):
        # Return an 'installable plugin info' object from a plugin_id, or raise
        # a KeyError if no such plugin is found
        installable_plugins = self.list_installable()
        return installable_plugins[plugin_id]

    def list_installable(self) -> dict[str, Any]:
        """Return a dictionary of installable plugins, where keys are
        plugin identifier and values are dictionary of plugin information.

        The plugin information dictionary contains the following keys:
          filename -- the name of the package in which the plugin is packaged
          version -- the version of the package
          description -- the description of the package
          dsize -- the download size of the package, in bytes
          sha1sum -- a hex representation of the sha1sum of the package
          capabilities -- a dictionary where keys are string in format
            "vendor, model, version" and values are capabilities dictionary.

        Raise an Exception if the plugin definition file is invalid/corrupted.
        If this file is absent, no error is raised, and an empty dictionary
        is returned.

        Note that the returned dictionary contains unicode strings instead
        of 'normal' string.

        """
        try:
            with open(self._db_pathname()) as f:
                all_raw_plugin_info = json.load(f)
        except OSError:
            return {}

        localize_fun = _new_localize_fun()
        for plugin_id, raw_plugin_info in all_raw_plugin_info.items():
            _check_raw_plugin_info(
                raw_plugin_info, plugin_id, _PLUGIN_INFO_INSTALLABLE_KEYS
            )
            localize_fun(raw_plugin_info)
        return all_raw_plugin_info

    def is_installed(self, plugin_id: str) -> bool:
        """Return true if the plugin <plugin_id> is currently installed, else
        false.

        """
        return plugin_id in self.list_installed()

    def _get_installed_plugin_info(self, plugin_dir: str) -> dict[str, Any]:
        plugin_info_path = os.path.join(plugin_dir, _PLUGIN_INFO_FILENAME)
        with open(plugin_info_path) as f:
            return json.load(f)

    def list_installed(self) -> dict[str, Any]:
        """Return a dictionary of installed plugins, where keys are plugin
        identifier and value are dictionary of plugin information.

        See Plugin.info method for more information on the returned dictionary.

        """
        # we can't iterate over loaded plugins (i.e. self._plugins) here
        # because a plugin could be installed but not loaded (most common
        # case is when loading the plugins at the start). We might want to
        # rework a bit all this.
        localize_fun = _new_localize_fun()
        installed_plugins = {}
        for rel_plugin_dir in os.listdir(self._plugins_dir):
            abs_plugin_dir = os.path.join(self._plugins_dir, rel_plugin_dir)
            if os.path.isdir(abs_plugin_dir):
                raw_plugin_info = self._get_installed_plugin_info(abs_plugin_dir)
                _check_raw_plugin_info(
                    raw_plugin_info,
                    rel_plugin_dir,
                    _PLUGIN_INFO_INSTALLED_KEYS,
                )
                localize_fun(raw_plugin_info)
                installed_plugins[rel_plugin_dir] = raw_plugin_info
        return installed_plugins

    @staticmethod
    def _add_execfile(pg_globals, plugin_dir):
        # add 'execfile_' to pg_globals.
        def aux(filename, *args, **kwargs):
            if args:
                globals = args[0]
                args = args[1:]
            elif 'globals' in kwargs:
                globals = kwargs.pop('globals')
            else:
                globals = pg_globals
            # reinject execfile_ if not present
            if 'execfile_' not in globals:
                globals['execfile_'] = aux
            # if filename is relative, then it must be relative to the plugin dir
            if not os.path.isabs(filename):
                filename = os.path.join(plugin_dir, filename)
            with open(filename, 'rb') as f:
                exec(compile(f.read(), filename, 'exec'), globals, *args, **kwargs)

        pg_globals['execfile_'] = aux

    def _execplugin(self, plugin_dir, pg_globals):
        entry_file = os.path.join(plugin_dir, self._ENTRY_FILENAME)
        self._add_execfile(pg_globals, plugin_dir)
        logger.debug('Executing plugin entry file "%s"', entry_file)
        with open(entry_file, 'rb') as f:
            exec(compile(f.read(), entry_file, 'exec'), pg_globals)

    def attach(self, observer: AbstractPluginManagerObserver):
        """Attach an IPluginManagerObserver object to this plugin manager.

        Note that since observers are weakly referenced, you MUST keep a
        reference to each one somewhere in the application if you want them
        not to be immediately garbage collected.

        """
        logger.debug('Attaching plugin manager observer %s', observer)
        if observer in self._observers:
            logger.info('Observer %s was already attached', observer)
        else:
            self._observers[observer] = None

    def detach(self, observer):
        """Detach an IPluginManagerObserver object to this plugin manager."""
        logger.debug('Detaching plugin manager observer %s', observer)
        try:
            del self._observers[observer]
        except KeyError:
            logger.info('Observer %s was not attached', observer)

    def _notify(self, plugin_id, action):
        # action is either 'load' or 'unload'
        logger.debug('Notifying plugin manager observers: %s %s', action, plugin_id)
        for observer in self._observers:
            try:
                logger.info('Notifying plugin manager observer %s', observer)
                fun = getattr(observer, f'pg_{action}')
                fun(plugin_id)
            except Exception:
                logger.error(
                    'Error while notifying plugin manager observer %s',
                    observer,
                    exc_info=True,
                )

    def _load_and_notify(self, plugin_id: str, plugin: Plugin):
        self._plugins[plugin_id] = plugin
        self._notify(plugin_id, 'load')

    def _unload_and_notify(self, plugin_id: str):
        try:
            plugin = self._plugins.pop(plugin_id)
        except KeyError:
            raise PluginNotLoadedError(plugin_id)

        logger.info('Closing plugin %s', plugin_id)
        try:
            plugin.close()
        except Exception:
            logger.error('Error while closing plugin %s', plugin_id, exc_info=True)
        self._notify(plugin_id, 'unload')

    @staticmethod
    def _is_plugin_class(obj):
        # return true if obj is a plugin class with IS_PLUGIN true
        return (
            isinstance(obj, type)
            and (issubclass(obj, Plugin) or issubclass(obj, LegacyImportPlugin))
            and getattr(obj, 'IS_PLUGIN', None)
        )

    def load(
        self, plugin_id: str, gen_cfg: dict | None = None, spec_cfg: dict | None = None
    ):
        """Load a plugin.

        Raise an Exception if the plugin is already loaded, since we offer
        a guarantee to plugins that no more than one instance is active at any
        time.

        Also raise an Exception if the plugin could not be loaded, either
        because there's no plugin with such a id or because of an error
        at plugin load time.

        gen_cfg -- a mapping object with general configuration parameters.
          These parameters are the same for every plugin.
        spec_cfg -- a mapping object with plugin-specific configuration
          parameters. These parameters are specific to every plugin.

        """
        logger.info('Loading plugin %s', plugin_id)
        if plugin_id in self._plugins:
            raise Exception(f'plugin {plugin_id} is already loaded')

        plugin_dir = os.path.join(self._plugins_dir, plugin_id)
        plugin_info = self._get_installed_plugin_info(plugin_dir)
        if self._check_compat_min:
            min_compat = plugin_info.get('plugin_iface_version_min')
            if min_compat is not None and self.PLUGIN_IFACE_VERSION < min_compat:
                logger.error(
                    'Plugin %s is not compatible: %s < %s',
                    plugin_id,
                    self.PLUGIN_IFACE_VERSION,
                    min_compat,
                )
                raise Exception('plugin min compat not satisfied')
        if self._check_compat_max:
            max_compat = plugin_info.get('plugin_iface_version_max')
            if max_compat is not None and self.PLUGIN_IFACE_VERSION > max_compat:
                logger.error(
                    'Plugin %s is not compatible: %s > %s',
                    plugin_id,
                    self.PLUGIN_IFACE_VERSION,
                    max_compat,
                )
                raise Exception('plugin max compat not satisfied')
        plugin_globals: dict[str, Any] = {}
        self._execplugin(plugin_dir, plugin_globals)
        for obj in plugin_globals.values():
            if self._is_plugin_class(obj):
                break
        else:
            raise Exception(f'plugin {plugin_id} has no plugin class')
        logger.debug('Creating plugin instance from class %s', obj)
        plugin = obj(self._app, plugin_dir, gen_cfg, spec_cfg)
        plugin.id = plugin_id
        self._load_and_notify(plugin_id, plugin)

    def unload(self, plugin_id: str):
        """Unload a plugin.

        Raise a PluginNotLoadedError if the plugin is not loaded.

        """
        logger.info('Unloading plugin %s', plugin_id)
        self._unload_and_notify(plugin_id)

    # Dictionary-like methods for loaded plugin access

    def __contains__(self, key: str):
        return key in self._plugins

    def __iter__(self):
        return iter(self._plugins)

    def __getitem__(self, key: str):
        return self._plugins[key]

    def __len__(self):
        return len(self._plugins)

    def get(self, key, default=None):
        return self._plugins.get(key, default)

    def keys(self):
        return list(self._plugins)

    def items(self):
        yield from self._plugins.items()

    def values(self):
        yield from self._plugins.values()
