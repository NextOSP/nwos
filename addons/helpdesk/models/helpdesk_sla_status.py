# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, fields, models


class HelpdeskSLAStatus(models.Model):
    _name = 'helpdesk.sla.status'
    _description = 'Helpdesk SLA Status'
    _order = 'deadline asc, sla_stage_sequence asc'
    _rec_name = 'sla_id'

    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', required=True,
                                ondelete='cascade', index=True)
    sla_id = fields.Many2one('helpdesk.sla', string='SLA Policy', required=True,
                             ondelete='cascade')
    sla_stage_id = fields.Many2one('helpdesk.stage', related='sla_id.stage_id',
                                   string='Target Stage', store=True)
    sla_stage_sequence = fields.Integer(related='sla_id.stage_id.sequence', store=True)

    deadline = fields.Datetime(string='Deadline')
    reached_datetime = fields.Datetime(
        string='Reached Date',
        help='Datetime at which the ticket reached the SLA target stage.')
    status = fields.Selection([
        ('not_reached', 'In Progress'),
        ('reached', 'Reached'),
        ('failed', 'Failed'),
    ], string='Status', default='not_reached', required=True, index=True)
    reached_hours = fields.Float(
        string='Time to Reach (Hours)', compute='_compute_reached_hours', store=True,
        help='Hours between the ticket creation and the moment the SLA target '
             'stage was reached (elapsed time so far when still in progress).')
    exceeded_hours = fields.Float(
        string='Exceeded Working Hours', compute='_compute_exceeded_hours', store=True,
        help='Number of hours the ticket exceeded the SLA deadline by '
             '(zero when the deadline was met).')
    color = fields.Integer(string='Color Index', compute='_compute_color')

    @api.depends('reached_datetime', 'ticket_id.create_date')
    def _compute_reached_hours(self):
        for status in self:
            start = status.ticket_id.create_date
            end = status.reached_datetime or fields.Datetime.now()
            status.reached_hours = max(0.0, (end - start).total_seconds() / 3600.0) if start else 0.0

    @api.depends('deadline', 'reached_datetime', 'status')
    def _compute_exceeded_hours(self):
        for status in self:
            if status.deadline and status.reached_datetime and status.reached_datetime > status.deadline:
                status.exceeded_hours = (status.reached_datetime - status.deadline).total_seconds() / 3600.0
            elif status.status == 'failed' and status.deadline and not status.reached_datetime:
                status.exceeded_hours = (fields.Datetime.now() - status.deadline).total_seconds() / 3600.0
            else:
                status.exceeded_hours = 0.0

    @api.depends('status')
    def _compute_color(self):
        color_map = {'not_reached': 4, 'reached': 10, 'failed': 1}
        for status in self:
            status.color = color_map.get(status.status, 0)

    def _mark_reached(self, reached_datetime=None):
        reached_datetime = reached_datetime or fields.Datetime.now()
        for status in self:
            status.write({
                'reached_datetime': reached_datetime,
                'status': 'failed' if status.deadline and reached_datetime > status.deadline else 'reached',
            })

    def _mark_failed(self):
        self.write({'status': 'failed'})
