# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    stock_request_id = fields.Many2one(
        'stock.request', string='Stock Request', index=True, copy=False,
        help="Stock request that generated this purchase.")
