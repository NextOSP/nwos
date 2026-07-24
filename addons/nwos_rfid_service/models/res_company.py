from nwos import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    rfid_require_payment_before_delivery = fields.Boolean(
        string='Require Kit Payment Before Delivery',
        default=True,
        help='When enabled, Kit deliveries and installation tasks remain blocked '
             'until all Kit Item invoices are fully paid.')
    rfid_project_template_id = fields.Many2one(
        'project.project', string='Default Installation Project Template',
        domain=[('is_template', '=', True)])
    rfid_helpdesk_team_id = fields.Many2one(
        'helpdesk.team', string='Default Nextwaves Kit Helpdesk Team')

    def write(self, vals):
        result = super().write(vals)
        if (
            'rfid_require_payment_before_delivery' in vals
            and not vals['rfid_require_payment_before_delivery']
        ):
            waiting_sites = self.env['rfid.service.site'].search([
                ('company_id', 'in', self.ids),
                ('state', '=', 'awaiting_payment'),
                ('payment_released', '=', False),
            ])
            waiting_sites._refresh_payment_release()
        return result


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rfid_require_payment_before_delivery = fields.Boolean(
        related='company_id.rfid_require_payment_before_delivery',
        readonly=False)
    rfid_project_template_id = fields.Many2one(
        related='company_id.rfid_project_template_id', readonly=False)
    rfid_helpdesk_team_id = fields.Many2one(
        related='company_id.rfid_helpdesk_team_id', readonly=False)
