#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from setuptools import setup


setup(
    name='xivo_prov',
    version='1.0.0',

    description='Wazo provd test helpers',

    author='Wazo Authors',
    author_email='dev@wazo.community',
    packages=['xivo_provd_test_helpers'],
    package_dir={
        'xivo_provd_test_helpers': 'suite/helpers',
    }
)
