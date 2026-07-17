# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'NextBot Agent Runtime',
    'version': '2.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Durable planning, execution, approvals, memory and knowledge for NextBot',
    'website': 'https://github.com/NextOSP',
    'depends': ['mail_bot', 'attachment_indexation'],
    'data': [
        'security/nextbot_agent_security.xml',
        'security/ir.model.access.csv',
        'data/nextbot_agent_cron.xml',
        'views/nextbot_org_rule_views.xml',
        'views/nextbot_knowledge_views.xml',
        'views/res_config_settings_views.xml',
        'views/nextbot_agent_menus.xml',
    ],
    'installable': True,
    'application': False,
    # Part of the standard NWOS install: auto-install as soon as the bot
    # (mail_bot, itself auto-installed) is present.
    'auto_install': ['mail_bot'],
    'author': 'NextOSP',
    'license': 'LGPL-3',
}
