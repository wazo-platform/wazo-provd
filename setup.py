#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from distutils.core import setup

setup(
    name='provisioning',
    version='0.1',
    description='XIVO provisioning daemon',
    maintainer='Proformatique',
    maintainer_email='technique@proformatique.com',
    url='http://wiki.xivo.io/',
    license='GPLv3',

    packages=['provd',
              'provd.devices',
              'provd.persist',
              'provd.rest',
              'provd.rest.server',
              'provd.servers',
              'provd.servers.tftp',
              'twisted',
              'twisted.plugins'],
    package_data={'provd': ['tzinform/tzdatax'],
                  'twisted': ['.noinit'],
                  'twisted.plugins': ['provd_plugins.py', '.noinit']}
)
