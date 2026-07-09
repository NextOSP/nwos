# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_cl_sii_code = fields.Integer('SII Code', aggregator=False)
