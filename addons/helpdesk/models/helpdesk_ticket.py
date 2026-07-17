# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from nwos import api, fields, models, tools
from nwos.exceptions import UserError
from nwos.tools.translate import _


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _description = 'Helpdesk Ticket'
    _inherit = ['portal.mixin', 'mail.thread.cc', 'mail.activity.mixin', 'rating.mixin']
    _order = 'priority desc, id desc'
    _rec_names_search = ['name', 'ticket_ref']
    _primary_email = 'partner_email'
    _mail_post_access = 'read'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    name = fields.Char(string='Subject', required=True, index='trigram', tracking=True)
    ticket_ref = fields.Char(string='Ticket Reference', readonly=True, copy=False, index=True,
                             default=lambda self: _('New'))
    description = fields.Html(string='Description', sanitize=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index')
    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Ready'),
        ('blocked', 'Blocked'),
    ], string='Kanban State', default='normal', copy=False, required=True, tracking=True)

    # Customer
    partner_id = fields.Many2one('res.partner', string='Customer', index='btree_not_null',
                                 tracking=True, help='The customer who submitted the ticket.')
    partner_name = fields.Char(string='Customer Name', compute='_compute_partner_info',
                               store=True, readonly=False)
    partner_email = fields.Char(string='Customer Email', compute='_compute_partner_info',
                                store=True, readonly=False)
    partner_phone = fields.Char(string='Customer Phone', compute='_compute_partner_info',
                                store=True, readonly=False)
    commercial_partner_id = fields.Many2one(
        'res.partner', string='Commercial Entity',
        related='partner_id.commercial_partner_id', store=True)

    # Assignment / organisation
    team_id = fields.Many2one('helpdesk.team', string='Team', required=True, tracking=True,
                              index=True, default=lambda self: self._default_team_id())
    user_id = fields.Many2one('res.users', string='Assigned to', tracking=True, index=True,
                              compute='_compute_user_id', store=True, readonly=False,
                              domain="[('share', '=', False)]")
    stage_id = fields.Many2one(
        'helpdesk.stage', string='Stage', tracking=True, index=True, copy=False,
        compute='_compute_stage_id', store=True, readonly=False, ondelete='restrict',
        domain="['|', ('team_ids', '=', False), ('team_ids', 'in', team_id)]",
        group_expand='_read_group_stage_ids')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='0', required=True, tracking=True)
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags')
    company_id = fields.Many2one('res.company', string='Company',
                                 related='team_id.company_id', store=True, readonly=True)

    # Dates & performance
    create_date = fields.Datetime(string='Created on', readonly=True)
    assign_date = fields.Datetime(string='First Assignment Date', copy=False, readonly=True)
    closed_date = fields.Datetime(string='Closed on', copy=False, readonly=True)
    assign_hours = fields.Float(string='Time to First Assignment (Hours)',
                                compute='_compute_assign_hours', store=True)
    close_hours = fields.Float(string='Time to Close (Hours)',
                               compute='_compute_close_hours', store=True)
    open_hours = fields.Float(string='Open Time (Hours)', compute='_compute_open_hours')
    is_closed = fields.Boolean(string='Closed', related='stage_id.is_close', store=True)

    # SLA
    use_sla = fields.Boolean(related='team_id.use_sla')
    sla_ids = fields.Many2many('helpdesk.sla', string='SLA Policies',
                               compute='_compute_sla_ids', store=True)
    sla_status_ids = fields.One2many('helpdesk.sla.status', 'ticket_id', string='SLA Statuses',
                                     copy=False)
    sla_deadline = fields.Datetime(string='SLA Deadline', compute='_compute_sla_deadline',
                                   store=True,
                                   help='Earliest deadline of the SLA policies not yet reached.')
    sla_reached = fields.Boolean(string='SLA All Reached', compute='_compute_sla_state', store=True)
    sla_fail = fields.Boolean(string='SLA Failed', compute='_compute_sla_state', store=True)

    # ------------------------------------------------------------------
    # Defaults / group expand / constraints
    # ------------------------------------------------------------------
    @api.model
    def _default_team_id(self):
        team_id = self.env.context.get('default_team_id')
        if team_id:
            return self.env['helpdesk.team'].browse(team_id)
        return self.env['helpdesk.team'].search([
            ('member_ids', 'in', self.env.uid)], limit=1) or \
            self.env['helpdesk.team'].search([], limit=1)

    @api.model
    def _read_group_stage_ids(self, stages, domain, order=None):
        team_id = self.env.context.get('default_team_id')
        if team_id:
            return stages.search(['|', ('team_ids', '=', False), ('team_ids', 'in', team_id)])
        return stages.search([])

    @api.constrains('user_id', 'team_id')
    def _check_user_in_team(self):
        for ticket in self:
            if ticket.user_id and ticket.team_id.member_ids and \
                    ticket.user_id not in ticket.team_id.member_ids:
                raise UserError(_('The assigned user must be a member of team "%s".',
                                  ticket.team_id.name))

    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------
    @api.depends('team_id')
    def _compute_stage_id(self):
        for ticket in self:
            if not ticket.stage_id or (ticket.team_id.stage_ids and
                                       ticket.stage_id not in ticket.team_id.stage_ids):
                ticket.stage_id = ticket.team_id._determine_stage() if ticket.team_id else False

    @api.depends('team_id')
    def _compute_user_id(self):
        for ticket in self.filtered(lambda t: not t.user_id and t.team_id):
            ticket.user_id = ticket.team_id._determine_user_to_assign()

    @api.depends('partner_id')
    def _compute_partner_info(self):
        for ticket in self.filtered('partner_id'):
            ticket.partner_name = ticket.partner_id.name
            ticket.partner_email = ticket.partner_id.email
            ticket.partner_phone = ticket.partner_id.phone

    @api.depends('create_date', 'assign_date')
    def _compute_assign_hours(self):
        for ticket in self:
            if ticket.create_date and ticket.assign_date:
                ticket.assign_hours = max(0.0, (ticket.assign_date - ticket.create_date).total_seconds() / 3600.0)
            else:
                ticket.assign_hours = 0.0

    @api.depends('create_date', 'closed_date')
    def _compute_close_hours(self):
        for ticket in self:
            if ticket.create_date and ticket.closed_date:
                ticket.close_hours = max(0.0, (ticket.closed_date - ticket.create_date).total_seconds() / 3600.0)
            else:
                ticket.close_hours = 0.0

    def _compute_open_hours(self):
        now = fields.Datetime.now()
        for ticket in self:
            end = ticket.closed_date or now
            start = ticket.create_date or now
            ticket.open_hours = max(0.0, (end - start).total_seconds() / 3600.0)

    @api.depends('team_id', 'team_id.use_sla', 'priority', 'tag_ids', 'partner_id')
    def _compute_sla_ids(self):
        slas_per_team = {}
        for ticket in self:
            if not (ticket.team_id and ticket.team_id.use_sla):
                ticket.sla_ids = [fields.Command.clear()]
                continue
            if ticket.team_id not in slas_per_team:
                slas_per_team[ticket.team_id] = self.env['helpdesk.sla'].search(
                    [('team_id', '=', ticket.team_id.id)])
            slas = slas_per_team[ticket.team_id].filtered(lambda s: s._sla_find_domain(ticket))
            ticket.sla_ids = [fields.Command.set(slas.ids)]

    @api.depends('sla_status_ids.status', 'sla_status_ids.deadline')
    def _compute_sla_deadline(self):
        for ticket in self:
            deadlines = ticket.sla_status_ids.filtered(
                lambda s: s.status == 'not_reached' and s.deadline).mapped('deadline')
            ticket.sla_deadline = min(deadlines) if deadlines else False

    @api.depends('sla_status_ids.status')
    def _compute_sla_state(self):
        for ticket in self:
            statuses = ticket.sla_status_ids.mapped('status')
            ticket.sla_fail = 'failed' in statuses
            ticket.sla_reached = bool(statuses) and all(s == 'reached' for s in statuses)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = vals['name'].strip()
            if vals.get('ticket_ref', _('New')) == _('New'):
                vals['ticket_ref'] = self.env['ir.sequence'].next_by_code('helpdesk.ticket') or _('New')
            if vals.get('user_id'):
                vals['assign_date'] = now
        tickets = super().create(vals_list)
        for ticket in tickets:
            if ticket.user_id and not ticket.assign_date:
                ticket.assign_date = now
            if ticket.stage_id.is_close:
                ticket.closed_date = now
            if ticket.partner_id:
                ticket.message_subscribe(partner_ids=ticket.partner_id.ids)
        tickets._sla_apply()
        return tickets

    def write(self, vals):
        now = fields.Datetime.now()
        if vals.get('user_id'):
            self.filtered(lambda t: not t.assign_date).assign_date = now
        res = super().write(vals)
        if 'stage_id' in vals:
            self._sla_reach(now)
            closing = self.filtered(lambda t: t.stage_id.is_close)
            (closing - closing.filtered('closed_date')).closed_date = now
            (self - closing).filtered('closed_date').closed_date = False
        if any(f in vals for f in ('team_id', 'priority', 'tag_ids', 'partner_id')):
            self._sla_apply()
        if 'partner_id' in vals and vals['partner_id']:
            self.message_subscribe(partner_ids=[vals['partner_id']])
        return res

    def copy(self, default=None):
        default = dict(default or {}, name=_('%s (copy)', self.name))
        return super().copy(default)

    @api.depends('name', 'ticket_ref')
    def _compute_display_name(self):
        for ticket in self:
            if ticket.ticket_ref and ticket.ticket_ref != _('New'):
                ticket.display_name = f'{ticket.name} (#{ticket.ticket_ref})'
            else:
                ticket.display_name = ticket.name

    # ------------------------------------------------------------------
    # SLA business logic
    # ------------------------------------------------------------------
    def _sla_apply(self):
        """(Re)generate SLA statuses for the applicable SLA policies.

        Statuses of policies that no longer apply are removed unless already
        reached or failed; statuses in progress keep their original deadline.
        """
        SlaStatus = self.env['helpdesk.sla.status']
        status_vals = []
        for ticket in self:
            existing = {status.sla_id: status for status in ticket.sla_status_ids}
            for sla in ticket.sla_ids:
                if sla not in existing:
                    status_vals.append({
                        'ticket_id': ticket.id,
                        'sla_id': sla.id,
                        'deadline': ticket._sla_compute_deadline(sla),
                    })
            obsolete = ticket.sla_status_ids.filtered(
                lambda s: s.sla_id not in ticket.sla_ids and s.status == 'not_reached')
            obsolete.unlink()
        if status_vals:
            SlaStatus.create(status_vals)
        # a ticket created directly in an advanced stage may already satisfy
        # some of its SLA policies
        self._sla_reach(fields.Datetime.now())

    def _sla_compute_deadline(self, sla):
        """Deadline for an SLA policy, starting from the ticket creation and
        following the team's working schedule when one is set."""
        self.ensure_one()
        start = self.create_date or fields.Datetime.now()
        calendar = self.team_id.resource_calendar_id
        if calendar:
            deadline = calendar.plan_hours(sla._get_duration_hours(), start, compute_leaves=True)
            if deadline:
                return deadline
        return start + timedelta(days=sla.time_days, hours=sla.time_hours, minutes=sla.time_minutes)

    def _sla_reach(self, reached_datetime):
        """Mark as reached the SLA statuses whose target stage has been
        reached or passed (based on stage sequence)."""
        for ticket in self:
            if not ticket.stage_id:
                continue
            reached = ticket.sla_status_ids.filtered(
                lambda s: s.status == 'not_reached' and
                s.sla_stage_sequence <= ticket.stage_id.sequence)
            reached._mark_reached(reached_datetime)

    @api.model
    def _cron_check_sla_deadlines(self):
        """Mark overdue SLA statuses as failed."""
        overdue = self.env['helpdesk.sla.status'].search([
            ('status', '=', 'not_reached'),
            ('deadline', '<', fields.Datetime.now()),
        ])
        overdue._mark_failed()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def assign_ticket_to_self(self):
        self.ensure_one()
        self.user_id = self.env.user

    def action_close_ticket(self):
        """Move tickets to their team's first closing stage."""
        for ticket in self:
            stages = ticket.team_id.stage_ids or self.env['helpdesk.stage'].search([])
            closing_stage = stages.sorted('sequence').filtered('is_close')[:1]
            if not closing_stage:
                raise UserError(_('No closing stage is configured for team "%s".',
                                  ticket.team_id.name))
            ticket.stage_id = closing_stage

    def action_reopen_ticket(self):
        """Move tickets back to their team's first open stage."""
        for ticket in self:
            stage = ticket.team_id._determine_stage()
            if not stage or stage.is_close:
                raise UserError(_('No open stage is configured.'))
            ticket.stage_id = stage

    # ------------------------------------------------------------------
    # Mail gateway / tracking
    # ------------------------------------------------------------------
    def _creation_message(self):
        self.ensure_one()
        return _('Ticket created in team "%(team_name)s".', team_name=self.team_id.display_name)

    def _track_template(self, changes):
        res = super()._track_template(changes)
        ticket = self[0]
        if 'stage_id' in changes and ticket.stage_id.template_id:
            res['stage_id'] = (ticket.stage_id.template_id, {
                'auto_delete_keep_log': False,
                'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                'email_layout_xmlid': 'mail.mail_notification_light',
            })
        return res

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a ticket from an incoming email (team alias)."""
        create_context = dict(self.env.context or {})
        create_context['default_user_id'] = False
        if custom_values is None:
            custom_values = {}
        if not msg_dict.get('author_id') and msg_dict.get('email_from'):
            author = self.env['mail.thread']._partner_find_from_emails_single(
                [msg_dict['email_from']], no_create=True)
            if author:
                msg_dict['author_id'] = author.id
        defaults = {
            'name': msg_dict.get('subject') or _('No Subject'),
            'partner_id': msg_dict.get('author_id', False),
            'partner_email': tools.email_normalize(msg_dict.get('email_from') or '') or msg_dict.get('email_from'),
        }
        defaults.update(custom_values)
        ticket = super(HelpdeskTicket, self.with_context(create_context)).message_new(
            msg_dict, custom_values=defaults)
        partners = ticket._partner_find_from_emails_single(
            tools.email_split((msg_dict.get('to') or '') + ',' + (msg_dict.get('cc') or '')),
            no_create=True)
        ticket.message_subscribe(partners.ids)
        return ticket

    def message_update(self, msg_dict, update_vals=None):
        for ticket in self:
            partners = ticket._partner_find_from_emails_single(
                tools.email_split((msg_dict.get('to') or '') + ',' + (msg_dict.get('cc') or '')),
                no_create=True)
            ticket.message_subscribe(partners.ids)
        return super().message_update(msg_dict, update_vals=update_vals)

    # ------------------------------------------------------------------
    # Portal / Rating
    # ------------------------------------------------------------------
    def _compute_access_url(self):
        super()._compute_access_url()
        for ticket in self:
            ticket.access_url = '/helpdesk/ticket/%s' % ticket.id

    def _rating_get_partner(self):
        return self.partner_id

    def _rating_get_operator(self):
        return self.user_id or self.team_id.user_id

    def _get_rating_url(self, partner=None):
        self.ensure_one()
        return '/helpdesk/rating/%s/%s' % (self.id, self._portal_ensure_token())
