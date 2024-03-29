# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import warnings

import wazo_provd

warnings.simplefilter('module', category=DeprecationWarning)
warnings.warn(
    f'{__name__} is deprecated and will be removed in the future, '
    'Please use `wazo_provd` instead.',
    DeprecationWarning,
    stacklevel=2,
)

# Note: Alias provd to wazo_provd to keep plugins compatibility
sys.modules['provd'] = wazo_provd
