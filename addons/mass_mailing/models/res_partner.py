# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models


class ResPartner(models.Model):
    _inherit = 'res.partner'
    _mailing_enabled = True
