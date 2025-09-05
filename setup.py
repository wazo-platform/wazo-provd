#!/usr/bin/env python3
# Copyright 2008-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import find_packages, setup

setup(
    name='wazo-provd',
    version='0.2',
    description='Wazo provisioning daemon',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    url='http://wazo.community',
    license='GPLv3',
    packages=find_packages(exclude=['*.tests']) + ['twisted', 'twisted.plugins'],
    package_data={
        'wazo_provd': ['rest/api/api.yml'],
        'twisted': ['.noinit'],
        'twisted.plugins': ['provd_plugins.py', '.noinit'],
    },
)
