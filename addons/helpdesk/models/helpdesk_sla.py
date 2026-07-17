# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, fields, models


class HelpdeskSLA(models.Model):
    _name = 'helpdesk.sla'
    _description = 'Helpdesk SLA Policy'
    _order = 'name'

    name = fields.Char(string='SLA Policy Name', required=True, translate=True)
    description = fields.Html(string='SLA Policy Description', translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='team_id.company_id', store=True, readonly=True)

    # Criteria
    team_id = fields.Many2one('helpdesk.team', string='Team', required=True,
                              help='The team this SLA policy applies to.')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Minimum Priority', default='0', required=True,
        help='The SLA policy only applies to tickets of this priority or higher.')
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags',
                               help='If set, the SLA policy only applies to tickets '
                                    'having all of these tags.')
    partner_ids = fields.Many2many('res.partner', string='Customers',
                                   help='If set, the SLA policy only applies to '
                                        'tickets of these customers.')

    # Target
    stage_id = fields.Many2one(
        'helpdesk.stage', string='Target Stage', required=True,
        help='The ticket must reach this stage (or any later one) before the deadline.')
    exclude_stage_ids = fields.Many2many(
        'helpdesk.stage', string='Excluded Stages',
        domain="[('id', '!=', stage_id)]",
        help='Time spent in these stages is not taken into account when '
             'computing the SLA deadline.')
    time_days = fields.Integer(string='Days', default=0,
                               help='Days to reach the target stage, based on the '
                                    "team's working schedule.")
    time_hours = fields.Integer(string='Hours', default=0)
    time_minutes = fields.Integer(string='Minutes', default=0)

    @api.depends('team_id')
    def _compute_display_name(self):
        for sla in self:
            sla.display_name = f'{sla.name} - {sla.team_id.name}' if sla.team_id else sla.name

    def _get_duration_hours(self):
        """Total SLA allowance expressed in hours."""
        self.ensure_one()
        return self.time_days * 24 + self.time_hours + self.time_minutes / 60.0

    def _sla_find_domain(self, ticket):
        """Whether this SLA policy applies to the given ticket."""
        self.ensure_one()
        if ticket.team_id != self.team_id:
            return False
        if int(ticket.priority or '0') < int(self.priority):
            return False
        if self.tag_ids and not (self.tag_ids <= ticket.tag_ids):
            return False
        if self.partner_ids and ticket.partner_id not in self.partner_ids:
            return False
        return True
