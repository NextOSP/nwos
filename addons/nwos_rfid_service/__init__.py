from . import models


def post_init_hook(env):
    """Give every company usable defaults while keeping them configurable."""
    install_template = env.ref('nwos_rfid_service.rfid_installation_project_template', raise_if_not_found=False)
    helpdesk_team = env.ref('nwos_rfid_service.rfid_helpdesk_team', raise_if_not_found=False)
    values = {
        'rfid_project_template_id': install_template.id if install_template else False,
        'rfid_helpdesk_team_id': helpdesk_team.id if helpdesk_team else False,
    }
    for company in env['res.company'].search([]):
        company.write({key: value for key, value in values.items() if value and not company[key]})
