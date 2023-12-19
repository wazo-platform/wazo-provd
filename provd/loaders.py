# Copyright 2011-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Extension to the jinja2.loaders module."""
from __future__ import annotations

from collections.abc import Sequence
from itertools import chain
from os import walk
from os.path import getmtime, join, sep

from jinja2.exceptions import TemplateNotFound
from jinja2.loaders import BaseLoader, split_template_path
from jinja2.utils import open_if_exists


def _new_mtime_map(directories: str | Sequence[str]) -> dict[str, float]:
    # Return a dictionary where keys are pathname and values are last
    # modification times
    if isinstance(directories, str):
        directories = [directories]
    mtime_map: dict[str, float] = {}
    for directory in directories:
        for dirpath, dirnames, filenames in walk(directory):
            for pathname in chain(dirnames, filenames):
                abs_pathname = join(dirpath, pathname)
                try:
                    mtime_map[abs_pathname] = getmtime(abs_pathname)
                except OSError:
                    pass
    return mtime_map


class ProvdFileSystemLoader(BaseLoader):
    """A custom file system loader that does some extra check to templates
    'up to date' status to make sure that a custom template will always
    override a base template.

    """

    def __init__(self, searchpath, encoding='utf-8'):
        if isinstance(searchpath, str):
            searchpath = [searchpath]
        self._searchpath = list(searchpath)
        self._encoding = encoding

    def get_source(self, environment, template):
        pieces = split_template_path(template)
        for searchpath in self._searchpath:
            filename = join(searchpath, *pieces)
            f = open_if_exists(filename)
            if f is None:
                continue
            try:
                contents = f.read().decode(self._encoding)
            finally:
                f.close()

            mtime_map = _new_mtime_map(self._searchpath)

            def uptodate():
                return mtime_map == _new_mtime_map(self._searchpath)

            return contents, filename, uptodate
        raise TemplateNotFound(template)

    def list_templates(self) -> list[str]:
        found: set[str] = set()
        for searchpath in self._searchpath:
            for dirpath, _, filenames in walk(searchpath):
                for filename in filenames:
                    template = (
                        join(dirpath, filename)[len(searchpath) :]
                        .strip(sep)
                        .replace(sep, '/')
                    )
                    if template[:2] == './':
                        template = template[2:]
                    if template not in found:
                        found.add(template)
        return sorted(found)
