# -*- coding: utf-8 -*-
from nwos import _, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    econtract_count = fields.Integer(compute='_compute_econtract_count')

    def _compute_econtract_count(self):
        data = self.env['econtract.contract']._read_group(
            [('res_model', '=', 'purchase.order'), ('res_id', 'in', self.ids)],
            ['res_id'], ['__count'])
        mapping = {res_id: count for res_id, count in data}
        for order in self:
            order.econtract_count = mapping.get(order.id, 0)

    def action_create_econtract(self):
        self.ensure_one()
        return self.env['econtract.generate.wizard'].action_open(self)

    def action_view_econtracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts'),
            'res_model': 'econtract.contract',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', 'purchase.order'), ('res_id', '=', self.id)],
            'context': {'create': False},
        }
