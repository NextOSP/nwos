# -*- coding: utf-8 -*-
from nwos import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_create_econtract(self):
        self.ensure_one()
        return self.env['econtract.generate.wizard'].action_open(self)
