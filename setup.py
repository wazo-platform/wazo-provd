#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from setuptools import setup
from setuptools import find_packages

setup(
    name='provisioning',
    version='0.2',
    description='XiVO provisioning daemon',
    maintainer='Proformatique',
    maintainer_email='technique@proformatique.com',
    url='http://github.com/wazo-pbx/xivo-provisioning',
    license='GPLv3',

    packages=find_packages(exclude=['*.tests']) + ['twisted', 'twisted.plugins'],
    package_data={'provd': ['tzinform/tzdatax'],
                  'twisted': ['.noinit'],
                  'twisted.plugins': ['provd_plugins.py', '.noinit']}
)
