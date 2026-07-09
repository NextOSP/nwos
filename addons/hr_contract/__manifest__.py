# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employee Contracts',
    'version': '1.0',
    'category': 'Human Resources/Contracts',
    'sequence': 335,
    'description': """
Add all information on the employee form to manage contracts.
=============================================================

    * Contract
    * Place of Birth,
    * Medical Examination Date
    * Company Vehicle

You can assign several contracts per employee.
    """,
    'website': 'https://github.com/NextOSP',
    'depends': ['hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/hr_contract_data.xml',
        'report/hr_contract_history_report_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_employee_views.xml',
        'views/resource_calendar_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/hr_departure_wizard_views.xml',
    ],
    'demo': ['data/hr_contract_demo.xml'],
    # NWOS19: the standalone 'hr.contract' model and 'hr.employee.base' were removed;
    # contracts were merged into core's 'hr.version' architecture. Making this install
    # would require a functional rewrite onto hr.version, so the legacy module is disabled.
    'installable': False,
    'application': True,
    'uninstall_hook': "uninstall_hook",
    'assets': {
        'web.assets_backend': [
            'hr_contract/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
