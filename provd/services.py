# Copyright 2010-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Standardized service definition and helper."""
from __future__ import annotations

import json
import logging
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from provd.operation import OperationInProgress

logger = logging.getLogger(__name__)


class InvalidParameterError(Exception):
    pass


class AbstractConfigurationService(metaclass=ABCMeta):
    """Interface for a "configuration service".

    This service offers an easy way to discover a certain number of "parameters"
    exposed by an underlying object, get the values of these parameters and
    set these parameters to new values, without previous knowledge of the
    underlying object. With this, it's possible to parameterize objects in a
    generic way.

    Note that when the word string is used here, it means unicode strings,
    not "raw" strings.

    To keep it as simple as possible, parameter names must match [\w.-]+. and
    parameters values must not contain any newline characters.

    """

    @abstractmethod
    def get(self, name: str) -> str | None:
        """Return the value associated with a parameter.

        The object returned MUST be a string, or None if there's no value
        associated with the parameter. This means the None value can't be a
        valid value for a parameter.

        Raise a KeyError if name is not a known valid parameter name.

        """

    @abstractmethod
    def set(self, name: str, value: str | None) -> None:
        """Associate a value with a parameter.

        The value MUST be a string, or None if there's no value to associate
        with the parameter.

        Raise a KeyError if name is not a known valid parameter.

        Raise an InvalidParameterError if the value for this parameter is not
        valid/acceptable. This means None has a special meaning and can't
        be used as a value.
        """

    @property
    @abstractmethod
    def description(self) -> tuple[str, str | None]:
        """A read-only list of tuple where the first element is the name of
        the parameter that can be set and the second element is a short
        description of the parameter.

        If a parameter has no description, the second element MUST be None.

        Localized description can also be given, which has the same structure
        as this attribute but with the name 'description_<locale>', i.e.
        'description_fr' for example.
        """


class AbstractInstallationService(metaclass=ABCMeta):
    """Interface for an installation service.

    It offers a download/install/uninstall service, where files can be
    downloaded and manipulated in a way they can be used by the plugin to
    offer extra functionalities.

    This service is useful/necessary if some files that a plugin use
    can't be bundled with it because it doesn't have the right to distribute
    these files, or because they are optional and the plugin want to
    let the choice to the user.

    """

    @abstractmethod
    def install(self, pkg_id: str) -> tuple[Deferred, OperationInProgress]:
        """Install a package.

        The package SHOULD be reinstalled even if it seemed to be installed.

        Return a tuple (deferred, operation in progress).

        Raise an Exception if there's already an installation in progress for the package.

        Raise an Exception if pkg_id is unknown.

        """

    @abstractmethod
    def uninstall(self, pkg_id: str) -> None:
        """Uninstall a package.

        Raise an Exception if pkg_id is unknown.

        """

    @abstractmethod
    def list_installable(self):
        """Return a dictionary of installable packages, where keys are
        package identifier and values are dictionary of package information.

        The package information dictionary can contain the following keys,
        which are all optional:
          dsize -- the download size of the package, in bytes
          isize -- the installed size of the package, in bytes
          version -- the version of the package
          description -- the description of the package

        """

    @abstractmethod
    def list_installed(self):
        """Return a dictionary of installed packages, where keys are package
        identifier and value are dictionary of package information.

        The package information dictionary can contain the following keys,
        which are all optional:
          version -- the version of the package
          description -- the description of the package

        """
    def upgrade(self, pkg_id):
        """Upgrade a package (optional operation).

        Interface similar to the one for the 'install' method.

        If the operation is not available, the method should not be defined.

        """

    def update(self):
        """Update the list of installable package (optional operation).

        Return a tuple (deferred, operation in progress).

        Raise an Exception if there's already an update operation in progress.

        If the operation is not available, the method should not be defined.

        """


# Some base service implementation

class AbstractConfigurationServiceParameter:
    description: str | None

    @abstractmethod
    def get(self) -> Any:
        """Get the value of this parameter."""

    @abstractmethod
    def set(self, value: Any) -> None:
        """Set the value of this parameter."""


class AttrConfigurationServiceParameter(AbstractConfigurationServiceParameter):
    def __init__(self, obj, name, description=None, check_fun=None, **kwargs):
        # kwargs is used to set localized description for example "description_fr='bonjour'"
        self._obj = obj
        self._name = name
        self.description = description
        self._check_fun = check_fun
        self.__dict__.update(kwargs)

    def get(self):
        return getattr(self._obj, self._name)

    def set(self, value):
        if self._check_fun is not None:
            self._check_fun(value)
        setattr(self._obj, self._name, value)


class DictConfigurationServiceParameter(AbstractConfigurationServiceParameter):
    # Note that this deletes the key from the dict when setting a None valueIInstallService

    def __init__(self, dict_: dict, key: Any, description: str = None, check_fun: Callable = None, **kwargs: Any):
        # kwargs is used to set localized description, for example "description_fr='bonjour'"
        self._dict = dict_
        self._key = key
        self.description = description
        self._check_fun = check_fun
        self.__dict__.update(kwargs)

    def get(self) -> Any:
        return self._dict.get(self._key)

    def set(self, value: Any) -> None:
        if self._check_fun is not None:
            self._check_fun(value)
        if value is None:
            if self._key in self._dict:
                del self._dict[self._key]
        else:
            self._dict[self._key] = value


class BaseConfigurationService(AbstractConfigurationService):
    def __init__(self, params: dict):
        """
        params -- a dictionary object where keys are parameter names and
          values are AbstractConfigurationService objects. After a call to this
          method, the params object belong to this object.

        Note that right now if you want a specific order in the description,
        you need to pass an ordered dict...

        """
        self._params = params

    def get(self, name: str) -> Any:
        param = self._params[name]
        return param.get()

    def set(self, name: str, value: Any) -> None:
        param = self._params[name]
        param.set(value)

    @property
    def description(self) -> list[tuple[str, str]]:
        return [(k, v.description) for k, v in self._params.items()]

    def __getattr__(self, name: str):
        # used to implement the localized description
        if not name.startswith('description_'):
            raise AttributeError(name)
        description_dict = [
            (k, getattr(v, name)) for k, v in self._params.items() if hasattr(v, name)
        ]
        if not description_dict:
            raise AttributeError(name)
        return description_dict


class PersistentConfigurationServiceDecorator:
    # Add persistence to a configuration service.
    # This is quite ad-hoc, and something more centralized with something a
    # bit more elaborated could be better on certain point, but since our
    # needs is low currently, this might be just fine.
    def __init__(self, cfg_service, persister):
        self._cfg_service = cfg_service
        self._persister = persister
        self._load_params()

    def _load_params(self):
        params = self._persister.params()
        for name, value in params.items():
            logger.debug('Setting configure param %s to %s', name, value)
            try:
                self._cfg_service.set(name, value)
            except KeyError as e:
                logger.info('Could not set unknown parameter "%s"', name)
            except InvalidParameterError as e:
                logger.warning('Invalid value "%s" for parameter "%s": %s',
                               value, name, e)

    def get(self, name: str) -> Any:
        return self._cfg_service.get(name)

    def set(self, name: str, value: Any) -> None:
        self._cfg_service.set(name, value)
        self._persister.update(name, value)

    def __getattr__(self, name: str) -> Any:
        # used for description and localized description
        return getattr(self._cfg_service, name)


class JsonConfigPersister:
    def __init__(self, filename: str) -> None:
        self._filename = filename
        self._cache = {}
        self._load()

    def _load(self):
        try:
            with open(self._filename) as f:
                self._cache = json.load(f)
        except IOError as e:
            logger.debug('Could not load file %s: %s', self._filename, e)
        except ValueError as e:
            logger.warning('Invalid content in file %s: %s', self._filename, e)

    def _save(self) -> None:
        with open(self._filename, 'w') as f:
            json.dump(self._cache, f)

    def params(self) -> dict:
        # Return every persisted parameter as a dictionary of parameters
        # names and values.
        return dict(self._cache)

    def update(self, name: str, value: Any) -> None:
        self._cache[name] = value
        self._save()
