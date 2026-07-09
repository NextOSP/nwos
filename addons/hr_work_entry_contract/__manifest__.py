#-*- coding:utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'Work Entries - Contract',
    'category': 'Human Resources/Employees',
    'sequence': 39,
    'summary': 'Manage work entries',
    # NWOS19: depends on the legacy 'hr_contract'/'hr.contract' model which was removed
    # (contracts merged into 'hr.version'). In NWOS 19 this functionality lives in
    # core hr_work_entry. Disabled until rewritten onto the hr.version architecture.
    'installable': False,
    'depends': [
        'hr_work_entry',
        'hr_contract',
    ],
    'data': [
        'security/hr_work_entry_security.xml',
        'security/ir.model.access.csv',
        'data/hr_work_entry_data.xml',
        'data/ir_cron_data.xml',
        'views/hr_work_entry_views.xml',
        'views/hr_contract_views.xml',
        'wizard/hr_work_entry_regeneration_wizard_views.xml',
    ],
    'demo': [
        'data/hr_work_entry_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_work_entry_contract/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
