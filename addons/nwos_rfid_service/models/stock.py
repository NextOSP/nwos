from nwos import api, fields, models, _
from nwos.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    rfid_site_id = fields.Many2one(
        'rfid.service.site', string='Nextwaves Kit Site', index=True, copy=True)

    def _key_assign_picking(self):
        return super()._key_assign_picking() + (self.rfid_site_id,)

    def _search_picking_for_assignation_domain(self):
        return super()._search_picking_for_assignation_domain() + [
            ('rfid_site_id', '=', self.rfid_site_id.id)
        ]

    def _get_new_picking_values(self):
        values = super()._get_new_picking_values()
        site = self.mapped('rfid_site_id')
        if len(site) == 1:
            values.update({
                'rfid_site_id': site.id,
                'partner_id': site.installation_address_id.id,
                'project_id': site.installation_project_id.id,
            })
        return values

    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        if self.rfid_site_id:
            values['rfid_site_id'] = self.rfid_site_id.id
            values['partner_id'] = self.rfid_site_id.installation_address_id.id
        return values

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        return super()._prepare_merge_moves_distinct_fields() + ['rfid_site_id']


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_custom_move_fields(self):
        return super()._get_custom_move_fields() + ['rfid_site_id']


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    rfid_site_id = fields.Many2one(
        'rfid.service.site', string='Nextwaves Kit Site', index=True, copy=True)
    rfid_payment_blocked = fields.Boolean(
        related='rfid_site_id.payment_blocked', string='Kit Payment Blocked')

    def action_assign(self):
        result = super().action_assign()
        self.filtered(
            lambda picking: picking.rfid_site_id
            and picking.picking_type_id.code == 'outgoing'
            and picking.state in ('assigned', 'confirmed', 'waiting')
            and picking.rfid_site_id.state == 'ready'
        ).mapped('rfid_site_id').write({'state': 'in_delivery'})
        return result

    def button_validate(self):
        blocked = self.filtered(
            lambda picking: picking.rfid_site_id
            and picking.picking_type_id.code == 'outgoing'
            and picking.rfid_site_id.payment_blocked
        )
        if blocked:
            raise UserError(_(
                'Kit payment has not been released for site(s): %s',
                ', '.join(blocked.mapped('rfid_site_id.display_name')),
            ))
        result = super().button_validate()
        if result is True:
            for picking in self.filtered(
                    lambda record: record.rfid_site_id
                    and record.picking_type_id.code == 'outgoing'
                    and record.state == 'done'):
                if picking.rfid_site_id.state in ('ready', 'in_delivery'):
                    picking.rfid_site_id.state = 'in_installation'
        return result
