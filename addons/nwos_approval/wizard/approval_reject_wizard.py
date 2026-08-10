# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import _, fields, models
from nwos.exceptions import UserError


class ApprovalRejectWizard(models.TransientModel):
    _name = 'approval.reject.wizard'
    _description = 'Refuse an Approval'

    request_id = fields.Many2one(
        'approval.request', string='Approval Request', required=True,
        ondelete='cascade')
    step_id = fields.Many2one('approval.step', string='Step')
    document_name = fields.Char(related='request_id.res_name', readonly=True)
    reason = fields.Text(string='Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        request = self.request_id
        step = self.step_id or request.current_step_id
        if step and not step._user_can_approve():
            raise UserError(_(
                "You cannot refuse this step (not an approver, or not the "
                "current step)."))
        request.sudo()._reject(self.reason, step=step)
        return {'type': 'ir.actions.act_window_close'}
