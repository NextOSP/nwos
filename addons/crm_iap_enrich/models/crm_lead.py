# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    iap_enrich_done = fields.Boolean(string='Enrichment done', help='Legacy field kept for compatibility.')
    show_enrich_button = fields.Boolean(string='Allow manual enrich', compute="_compute_show_enrich_button")

    @api.depends('email_from', 'probability', 'iap_enrich_done', 'reveal_id')
    def _compute_show_enrich_button(self):
        for lead in self:
            lead.show_enrich_button = False

    @api.model
    def _iap_enrich_leads_cron(self, enrich_hours_delay=24, batch_size=50):
        return True

    def iap_enrich(self, *, batch_size=50):
        return True

    @api.model
    def _iap_enrich_from_response(self, iap_response):
        return True

    def _merge_get_fields_specific(self):
        return {
            **super()._merge_get_fields_specific(),
            'iap_enrich_done': lambda fname, leads: any(lead.iap_enrich_done for lead in leads),
        }
