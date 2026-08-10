# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
"""Gate tests: the registry patch, blocking, and resuming the blocked call."""
from nwos.tests.common import tagged

from ..models.approval_rule import BYPASS_KEY
from .common import ApprovalCommon


@tagged('post_install', '-at_install')
class TestApprovalGate(ApprovalCommon):

    def test_patch_is_installed_and_removed(self):
        key = ('res.partner', 'action_archive')
        rule = self._make_rule()
        self.assertIn(key, self.env.registry.__dict__['_nwos_approval_patched'])
        rule.unlink()
        self.assertNotIn(
            key, self.env.registry.__dict__.get('_nwos_approval_patched', set()))

    def test_gate_blocks_without_running_the_action(self):
        self._make_rule()
        partner = self._make_partner()
        result = partner.action_archive()
        self.assertTrue(partner.active,
                        "The gated action must not have run")
        self.assertEqual(result.get('tag'), 'display_notification')
        approval = self._approval_of(partner)
        self.assertEqual(approval.state, 'pending',
                         "Blocking must not roll back the approval request")

    def test_approval_resumes_the_action(self):
        self._make_rule()
        partner = self._make_partner()
        partner.action_archive()
        approval = self._approval_of(partner)
        approval.step_ids.with_user(self.approver).action_approve_step()
        partner.invalidate_recordset()
        self.assertFalse(partner.active, "The action should have re-run")
        self.assertEqual(approval.state, 'done')

    def test_resume_runs_as_the_requester(self):
        rule = self._make_rule(
            requester_field_id=self.env['ir.model.fields']._get(
                'res.partner', 'user_id').id)
        partner = self._make_partner(user_id=self.requester.id)
        partner.action_archive()
        approval = self._approval_of(partner)
        self.assertEqual(approval.requester_id, self.requester)
        approval.step_ids.with_user(self.approver).action_approve_step()
        partner.invalidate_recordset()
        self.assertFalse(partner.active)
        self.assertTrue(rule)

    def test_second_click_while_pending_does_not_duplicate(self):
        self._make_rule()
        partner = self._make_partner()
        partner.action_archive()
        partner.action_archive()
        self.assertEqual(self.env['approval.request'].search_count([
            ('res_model', '=', 'res.partner'), ('res_id', '=', partner.id),
        ]), 1)
        self.assertTrue(partner.active)

    def test_manual_reclick_consumes_an_approved_request(self):
        """Safety net: an approved-but-not-resumed request lets the click pass."""
        rule = self._make_rule()
        partner = self._make_partner()
        request = self.env['approval.request']._request_approval(
            partner, 'action_archive', rule)
        request.step_ids.write({'status': 'approved'})
        request.write({'state': 'approved'})
        partner.action_archive()
        partner.invalidate_recordset()
        self.assertFalse(partner.active)
        self.assertEqual(request.state, 'done')

    def test_bypass_context_skips_the_gate(self):
        self._make_rule()
        partner = self._make_partner()
        partner.with_context(
            **{BYPASS_KEY: ('res.partner.action_archive',)}).action_archive()
        partner.invalidate_recordset()
        self.assertFalse(partner.active)
        self.assertFalse(self._approval_of(partner))

    def test_partial_recordset_is_split(self):
        """Records that need approval are held back; the others go through."""
        self._make_rule(condition_domain="[('is_company', '=', True)]")
        company = self._make_partner(name='ACME', is_company=True)
        person = self._make_partner(name='Joe', is_company=False)
        (company | person).action_archive()
        (company | person).invalidate_recordset()
        self.assertTrue(company.active, "The company needs approval first")
        self.assertFalse(person.active, "The person was not gated")

    def test_rejection_does_not_run_the_action(self):
        self._make_rule()
        partner = self._make_partner()
        partner.action_archive()
        approval = self._approval_of(partner)
        self.env['approval.reject.wizard'].with_user(self.approver).create({
            'request_id': approval.id,
            'step_id': approval.current_step_id.id,
            'reason': 'No',
        }).action_confirm()
        partner.invalidate_recordset()
        self.assertTrue(partner.active)
        self.assertEqual(approval.state, 'rejected')

    def test_auto_approved_action_runs_immediately(self):
        self._make_rule(
            amount_field_id=self.env['ir.model.fields']._get(
                'res.partner', 'credit_limit').id,
            auto_ids=[(0, 0, {'name': 'small', 'max_amount': 100.0,
                              'scope': 'all'})])
        partner = self._make_partner(credit_limit=10.0)
        partner.action_archive()
        partner.invalidate_recordset()
        self.assertFalse(partner.active)
        self.assertEqual(self._approval_of(partner).state, 'done')

    def test_session_info_lists_gated_models(self):
        self._make_rule()
        self.assertIn('res.partner',
                      self.env['approval.request'].approval_models())
