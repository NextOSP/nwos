# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import fields, models


class HelpdeskStage(models.Model):
    _name = 'helpdesk.stage'
    _description = 'Helpdesk Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    fold = fields.Boolean(string='Folded in Kanban',
                          help='This stage is folded in the kanban view when '
                               'there are no records in that stage to display.')
    is_close = fields.Boolean(string='Closing Stage',
                              help='Tickets in this stage are considered as done.')
    is_solved = fields.Boolean(string='Solved Stage',
                               help='Tickets in this stage are considered solved successfully.')
    color = fields.Integer(string='Color Index')
    team_ids = fields.Many2many(
        'helpdesk.team', relation='team_stage_rel', string='Teams',
        help='Specific teams using this stage. Other teams will not be able '
             'to see or use this stage.')
    template_id = fields.Many2one(
        'mail.template', string='Email Template',
        domain=[('model', '=', 'helpdesk.ticket')],
        help='Automatically send this email to the customer when the ticket '
             'reaches this stage.')
    ticket_count = fields.Integer(string='Tickets', compute='_compute_ticket_count')

    def _compute_ticket_count(self):
        counts = self.env['helpdesk.ticket']._read_group(
            [('stage_id', 'in', self.ids)], ['stage_id'], ['__count'])
        count_map = {stage: count for stage, count in counts}
        for stage in self:
            stage.ticket_count = count_map.get(stage, 0)
