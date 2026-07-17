# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import fields, models


class DigestDigest(models.Model):
    _inherit = 'digest.digest'

    kpi_helpdesk_tickets = fields.Boolean(string='New Tickets')
    kpi_helpdesk_tickets_value = fields.Integer(compute='_compute_kpi_helpdesk_tickets_value')
    kpi_helpdesk_rating = fields.Boolean(string='Customer Rating')
    kpi_helpdesk_rating_value = fields.Float(compute='_compute_kpi_helpdesk_rating_value')

    def _compute_kpi_helpdesk_tickets_value(self):
        self._calculate_company_based_kpi(
            'helpdesk.ticket',
            'kpi_helpdesk_tickets_value',
        )

    def _compute_kpi_helpdesk_rating_value(self):
        start, end, __ = self._get_kpi_compute_parameters()
        for digest in self:
            tickets = self.env['helpdesk.ticket'].search([
                ('rating_last_value', '>', 0),
                ('closed_date', '>=', start or fields.Datetime.now()),
                ('closed_date', '<', end or fields.Datetime.now()),
            ])
            digest.kpi_helpdesk_rating_value = sum(t.rating_last_value for t in tickets) / len(tickets) if tickets else 0.0

    def _compute_kpis_actions(self, company, user):
        res = super(DigestDigest, self)._compute_kpis_actions(company, user)
        res['kpi_helpdesk_tickets'] = 'helpdesk.action_helpdesk_ticket_all'
        res['kpi_helpdesk_rating'] = 'helpdesk.action_helpdesk_ticket_all'
        return res
