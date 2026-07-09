# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def get_values(self):
        values = super().get_values()
        values['lead_enrich_auto'] = 'manual'
        return values

    def set_values(self):
        super().set_values()
        cron = self.sudo().with_context(active_test=False).env.ref('crm_iap_enrich.ir_cron_lead_enrichment', raise_if_not_found=False)
        if cron:
            cron.active = False
