# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _mailing_enabled = True
