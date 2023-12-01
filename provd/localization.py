# Copyright 2011-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Localization service.

A localization service holds the current locale and make it possible to
register callbacks with it so to be warned when the locale changes.

The word localization is used although that, at the time of writing this,
there's only basic support for multiple languages and not really any other
localization related things.

Valid locales are in the format language[_territory], i.e. 'fr' and 'fr_CA'
for example. We do not support the full POSIX locale identifiers (with codeset
and modifiers) as for now since there would be no use.

"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any
from weakref import WeakKeyDictionary

logger = logging.getLogger(__name__)

_L10N_SERVICE: LocalizationService | None = None
_LOCALE_REGEX = re.compile(r'^[a-z]{2,3}(?:_[A-Z]{2,3})?$')

# List of events
LOCALE_CHANGED = 'locale_changed'

Observer = Callable[[tuple[str, Any]], None]


class LocalizationService:
    def __init__(self, locale: str | None = None) -> None:
        self._locale = locale
        self._observers: WeakKeyDictionary[Observer, None] = WeakKeyDictionary()

    def attach_observer(self, observer: Observer) -> None:
        """Attach an observer to this localization service.

        Note that since observers are weakly referenced, you MUST keep a
        reference to each one somewhere in the application if you want them
        not to be immediately garbage collected.
        """
        logger.debug('Attaching localization observer %s', observer)
        if observer in self._observers:
            logger.info('Observer %s was already attached', observer)
        else:
            self._observers[observer] = None

    def detach_observer(self, observer: Observer) -> None:
        logger.debug('Detaching localization observer %s', observer)
        try:
            del self._observers[observer]
        except KeyError:
            logger.info('Observer %s was not attached', observer)

    def _notify(self, event: str, arg: Any) -> None:
        logger.debug('Notifying localization observers: %s %s', event, arg)
        for observer in self._observers:
            try:
                logger.info('Notifying localization observer %s', observer)
                observer((event, arg))
            except Exception:
                logger.error(
                    'Error while notifying observer %s', observer, exc_info=True
                )

    def set_locale(self, locale: str | None) -> None:
        """Set the current locale and fire a LOCALE_CHANGED event if the
        locale has changed.

        If locale is None, unset the current locale.

        Raise a ValueError if locale is not a valid locale, i.e. is malformed.

        """
        if locale is not None and not _LOCALE_REGEX.match(locale):
            raise ValueError(f'Invalid locale {locale}')
        if locale != self._locale:
            self._locale = locale
            self._notify(LOCALE_CHANGED, None)

    def get_locale(self) -> str | None:
        """Return the current locale.

        If no locale has been set, return None.

        """
        return self._locale

    def get_locale_and_language(self) -> tuple[str | None, str | None]:
        """Return a tuple (locale, language) of the current locale."""
        if self._locale is None:
            return None, None
        return self._locale, self._locale.split('_', 1)[0]


def register_localization_service(l10n_service: LocalizationService) -> None:
    logger.info('Registering localization service: %s', l10n_service)
    global _L10N_SERVICE
    _L10N_SERVICE = l10n_service


def unregister_localization_service() -> None:
    global _L10N_SERVICE
    if _L10N_SERVICE is not None:
        logger.info('Unregistering localization service: %s', _L10N_SERVICE)
        _L10N_SERVICE = None
    else:
        logger.info('No localization service registered')


def get_localization_service() -> LocalizationService | None:
    """Return the globally registered localization service or None if no
    localization service has been registered.

    """
    return _L10N_SERVICE


def get_locale() -> str | None:
    """Return the locale of the globally registered localization service or
    None if no localization service has been registered or no locale has
    been set.

    """
    l10n_service = _L10N_SERVICE
    if l10n_service is None:
        return None
    else:
        return l10n_service.get_locale()


def get_locale_and_language() -> tuple[str | None, str | None]:
    """Return the tuple (locale, language) of the globally registered
    localization service or (None, None) if no localization service has been
    registered or no locale has been set.

    """
    l10n_service = _L10N_SERVICE
    if l10n_service is None:
        return None, None
    return l10n_service.get_locale_and_language()
