# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import ast
from datetime import datetime, time, timedelta

from nwos import api, fields, models
from nwos.exceptions import ValidationError
from nwos.tools.translate import _


class HelpdeskTeam(models.Model):
    _name = 'helpdesk.team'
    _description = 'Helpdesk Team'
    _inherit = ['mail.alias.mixin', 'mail.thread', 'rating.parent.mixin']
    _order = 'sequence, name, id'
    _rating_satisfaction_days = 30

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    name = fields.Char(string='Team Name', required=True, translate=True)
    description = fields.Html(string='About Team', translate=True,
                              help='Description of the team shown to portal users.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    user_id = fields.Many2one('res.users', string='Team Leader', tracking=True,
                              default=lambda self: self.env.user,
                              domain="[('share', '=', False)]")
    member_ids = fields.Many2many(
        'res.users', string='Team Members', domain="[('share', '=', False)]",
        help='Users to whom tickets of this team can be assigned. '
             'Leave empty to allow any internal user.')

    # Assignment
    auto_assignment = fields.Boolean(string='Automatic Assignment',
                                     help='Automatically assign new tickets to team members.')
    assign_method = fields.Selection([
        ('randomly', 'Each user is assigned an equal number of tickets'),
        ('balanced', 'Each user has an equal number of open tickets'),
    ], string='Assignment Method', default='randomly', required=True,
        help='How new tickets are dispatched among team members:\n'
             '- Each user is assigned an equal number of tickets (round robin over all tickets)\n'
             '- Each user has an equal number of open tickets (balances the current workload)')

    # Stages & tickets
    stage_ids = fields.Many2many(
        'helpdesk.stage', relation='team_stage_rel', string='Stages',
        default=lambda self: self._default_stage_ids(),
        help="Stages the team will use. This team's tickets will only be able "
             'to reach these stages.')
    ticket_ids = fields.One2many('helpdesk.ticket', 'team_id', string='Ticket List')

    # SLA / working schedule
    use_sla = fields.Boolean(string='Use SLA Policies', default=True,
                             help="Track deadlines on this team's tickets based on SLA policies.")
    sla_ids = fields.One2many('helpdesk.sla', 'team_id', string='SLA Policies')
    resource_calendar_id = fields.Many2one(
        'resource.calendar', string='Working Hours',
        default=lambda self: self.env.company.resource_calendar_id,
        help='Working schedule used to compute SLA deadlines. '
             'If empty, deadlines are computed on calendar hours.')

    # Ticket counts
    ticket_count = fields.Integer(string='Tickets', compute='_compute_ticket_count')
    open_ticket_count = fields.Integer(string='Open Tickets', compute='_compute_ticket_count')
    unassigned_ticket_count = fields.Integer(string='Unassigned Tickets', compute='_compute_ticket_count')
    urgent_ticket_count = fields.Integer(string='Urgent Tickets', compute='_compute_ticket_count')
    failed_ticket_count = fields.Integer(string='Failed Tickets', compute='_compute_ticket_count')
    closed_ticket_count = fields.Integer(string='Tickets Closed', compute='_compute_ticket_count')

    # Performance
    sla_success_rate = fields.Float(string='SLA Success Rate', compute='_compute_sla_success_rate')
    avg_rating = fields.Float(string='Customer Rating', compute='_compute_avg_rating')

    # ------------------------------------------------------------------
    # Defaults / Constraints
    # ------------------------------------------------------------------
    @api.model
    def _default_stage_ids(self):
        return self.env['helpdesk.stage'].search([], order='sequence', limit=4)

    @api.constrains('auto_assignment', 'member_ids')
    def _check_auto_assignment_members(self):
        for team in self:
            if team.auto_assignment and not team.member_ids:
                raise ValidationError(_('Automatic assignment requires at least one team member.'))

    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------
    def _compute_ticket_count(self):
        domains = {
            'ticket_count': [],
            'open_ticket_count': [('is_closed', '=', False)],
            'unassigned_ticket_count': [('user_id', '=', False), ('is_closed', '=', False)],
            'urgent_ticket_count': [('priority', '=', '3'), ('is_closed', '=', False)],
            'failed_ticket_count': [('sla_fail', '=', True)],
            'closed_ticket_count': [('is_closed', '=', True)],
        }
        for field_name, domain in domains.items():
            counts = self.env['helpdesk.ticket']._read_group(
                domain + [('team_id', 'in', self.ids)],
                ['team_id'], ['__count']
            )
            count_map = {team: count for team, count in counts}
            for team in self:
                team[field_name] = count_map.get(team, 0)

    @api.depends('ticket_ids.is_closed', 'ticket_ids.sla_fail')
    def _compute_sla_success_rate(self):
        for team in self:
            tickets = team.ticket_ids.filtered(lambda t: t.is_closed and t.sla_status_ids)
            if not tickets:
                team.sla_success_rate = 100.0
                continue
            success = sum(1 for t in tickets if not t.sla_fail)
            team.sla_success_rate = (success / len(tickets)) * 100

    @api.depends('ticket_ids.rating_last_value', 'ticket_ids.rating_count')
    def _compute_avg_rating(self):
        for team in self:
            rated = team.ticket_ids.filtered(lambda t: t.rating_last_value > 0)
            team.avg_rating = sum(r.rating_last_value for r in rated) / len(rated) if rated else 0.0

    # ------------------------------------------------------------------
    # Mail alias
    # ------------------------------------------------------------------
    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values['alias_model_id'] = self.env['ir.model']._get_id('helpdesk.ticket')
        if self.id:
            values['alias_defaults'] = defaults = ast.literal_eval(self.alias_defaults or '{}')
            defaults['team_id'] = self.id
        return values

    # ------------------------------------------------------------------
    # Assignment / stage helpers
    # ------------------------------------------------------------------
    def _determine_user_to_assign(self):
        """Return the user a new ticket should be assigned to, following the
        team's assignment method, or an empty recordset when the team does
        not auto-assign."""
        self.ensure_one()
        if not (self.auto_assignment and self.member_ids):
            return self.env['res.users']
        members = self.member_ids
        if self.assign_method == 'balanced':
            domain = [('team_id', '=', self.id), ('user_id', 'in', members.ids),
                      ('is_closed', '=', False)]
        else:  # randomly: round robin over all tickets ever assigned
            domain = [('team_id', '=', self.id), ('user_id', 'in', members.ids)]
        counts = dict.fromkeys(members.ids, 0)
        for user, count in self.env['helpdesk.ticket']._read_group(domain, ['user_id'], ['__count']):
            counts[user.id] = count
        user_id = min(members.ids, key=lambda uid: (counts[uid], uid))
        return self.env['res.users'].browse(user_id)

    def _determine_stage(self):
        """First stage (lowest sequence) available for this team."""
        self.ensure_one()
        return self.stage_ids.sorted('sequence')[:1] or \
            self.env['helpdesk.stage'].search([], order='sequence', limit=1)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.model
    def retrieve_dashboard(self):
        """Aggregated KPIs for the Helpdesk Overview banner."""
        Ticket = self.env['helpdesk.ticket']
        result = {'open': {}, 'today': {}, 'last7': {}}

        open_domains = {
            'all': [('is_closed', '=', False)],
            'high': [('is_closed', '=', False), ('priority', '=', '2')],
            'urgent': [('is_closed', '=', False), ('priority', '=', '3')],
        }
        for key, domain in open_domains.items():
            tickets = Ticket.search(domain)
            count = len(tickets)
            result['open'][key] = {
                'count': count,
                'hours': sum(tickets.mapped('open_hours')) / count if count else 0.0,
                'failed': len(tickets.filtered('sla_fail')),
            }

        today_start = datetime.combine(fields.Date.context_today(self), time.min)
        for key, start, days in (('today', today_start, 1),
                                 ('last7', today_start - timedelta(days=6), 7)):
            closed = Ticket.search([('closed_date', '>=', start)])
            with_sla = closed.filtered('sla_status_ids')
            rated = closed.filtered(lambda t: t.rating_last_value > 0)
            result[key] = {
                'closed': len(closed) / (days if key == 'last7' else 1),
                'success_rate': (len(with_sla.filtered(lambda t: not t.sla_fail))
                                 / len(with_sla) * 100) if with_sla else None,
                'rating': (sum(rated.mapped('rating_last_value'))
                           / len(rated)) if rated else None,
            }
        return result

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tickets'),
            'res_model': 'helpdesk.ticket',
            'view_mode': 'kanban,list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id, 'search_default_open': 1},
        }
