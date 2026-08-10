# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos.tests.common import TransactionCase


class ApprovalCommon(TransactionCase):
    """Approval tests run against res.partner, a model every database has.

    `action_archive` is used as the gated action: it is a real, harmless,
    record-level button whose effect (active = False) is trivial to assert.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        # Both users may manage contacts: the gated action is res.partner's,
        # and the framework resumes it as the requester.
        cls.user_groups = [
            (4, cls.env.ref('base.group_user').id),
            (4, cls.env.ref('base.group_partner_manager').id),
            
        ]
        cls.approver = cls.env['res.users'].create({
            'name': 'Ann Approver', 'login': 'approval_ann',
            'group_ids': cls.user_groups,
        })
        cls.requester = cls.env['res.users'].create({
            'name': 'Ray Requester', 'login': 'approval_ray',
            'group_ids': cls.user_groups,
        })

    def _make_rule(self, **overrides):
        values = {
            'name': 'Archive needs approval',
            'res_model_id': self.partner_model.id,
            'method_name': 'action_archive',
            'step_ids': [(0, 0, {
                'name': 'Sign-off',
                'approver_type': 'users',
                'user_ids': [(6, 0, self.approver.ids)],
            })],
        }
        values.update(overrides)
        rule = self.env['approval.rule'].create(values)
        self.addCleanup(rule.unlink)
        return rule

    def _make_partner(self, **overrides):
        values = {'name': 'Test Partner'}
        values.update(overrides)
        return self.env['res.partner'].create(values)

    def _approval_of(self, record):
        return self.env['approval.request'].search([
            ('res_model', '=', record._name), ('res_id', '=', record.id),
        ], order='id desc', limit=1)
