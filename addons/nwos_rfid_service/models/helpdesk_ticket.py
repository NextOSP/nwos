from nwos import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    rfid_site_id = fields.Many2one(
        'rfid.service.site', string='Nextwaves Kit Site', index=True,
        domain="[('partner_id.commercial_partner_id', '=', commercial_partner_id)]")
    rfid_sale_order_id = fields.Many2one(
        related='rfid_site_id.sale_order_id', string='Sales Order')
    rfid_project_id = fields.Many2one(
        related='rfid_site_id.installation_project_id', string='Installation Project')
    rfid_activation_date = fields.Date(
        related='rfid_site_id.activation_date', string='Activation Date')
    rfid_installed_lot_ids = fields.Many2many(
        related='rfid_site_id.installed_lot_ids', string='Installed Serials / Lots')

    @api.onchange('rfid_site_id')
    def _onchange_rfid_site_id(self):
        if self.rfid_site_id:
            self.partner_id = self.rfid_site_id.partner_id
            self.team_id = self.rfid_site_id.company_id.rfid_helpdesk_team_id or self.team_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('rfid_site_id'):
                site = self.env['rfid.service.site'].browse(vals['rfid_site_id'])
                vals.setdefault('partner_id', site.partner_id.id)
                vals.setdefault('team_id', site.company_id.rfid_helpdesk_team_id.id)
        tickets = super().create(vals_list)
        for ticket in tickets.filtered(lambda record: record.partner_id and not record.rfid_site_id):
            sites = self.env['rfid.service.site'].search([
                ('partner_id.commercial_partner_id', '=', ticket.partner_id.commercial_partner_id.id),
                ('state', '=', 'active'),
            ], limit=2)
            if len(sites) == 1:
                ticket.rfid_site_id = sites
        return tickets
