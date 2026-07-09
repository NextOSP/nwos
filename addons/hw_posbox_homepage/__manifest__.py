# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'IoT Box Homepage',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'website': 'https://github.com/NextOSP',
    'summary': 'A homepage for the IoT Box',
    'description': """
IoT Box Homepage
================

This module overrides NWOS web interface to display a simple
Homepage that explains what's the iotbox and shows the status,
and where to find documentation.

If you activate this module, you won't be able to access the 
regular NWOS interface anymore.

""",
    'assets': {
        'web.assets_backend': [
            'hw_posbox_homepage/static/*/**',
        ],
    },
    'installable': False,
    'license': 'LGPL-3',
}
