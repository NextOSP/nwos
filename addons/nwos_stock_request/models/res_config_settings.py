# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_request_approval_amount = fields.Float(
        string='Stock Request Approval Amount',
        config_parameter='nwos_stock_request.approval_amount',
        help="Requests whose estimated total is below this amount can be "
             "self-approved by their requester. Above it, an approver is required. "
             "Set to 0 to always require an approver.")
