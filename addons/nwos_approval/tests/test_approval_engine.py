# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
"""Engine tests: rule matching, approver resolution, step semantics.

These never install the registry patch — they call `_request_approval()`
directly, so they stay fast and independent of the gate.
"""
from nwos.exceptions import ValidationError
from nwos.tests.common import tagged

from .common import ApprovalCommon


@tagged('post_install', '-at_install')
class TestApprovalEngine(ApprovalCommon):

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def test_domain_condition(self):
        rule = self._make_rule(condition_domain="[('is_company', '=', True)]")
        company = self._make_partner(name='ACME', is_company=True)
        person = self._make_partner(name='Joe', is_company=False)
        self.assertTrue(rule._matches(company))
        self.assertFalse(rule._matches(person))

    def test_amount_window(self):
        rule = self._make_rule(
            amount_field_id=self.env['ir.model.fields']._get(
                'res.partner', 'credit_limit').id,
            amount_min=100.0, amount_max=500.0)
        self.assertFalse(rule._matches(self._make_partner(credit_limit=50.0)))
        self.assertTrue(rule._matches(self._make_partner(credit_limit=200.0)))
        self.assertFalse(rule._matches(self._make_partner(credit_limit=900.0)),
                         "The upper bound is exclusive")

    def test_first_match_wins_by_sequence(self):
        second = self._make_rule(name='Second', sequence=20)
        first = self._make_rule(name='First', sequence=10)
        partner = self._make_partner()
        matched = self.env['approval.rule']._match(partner, 'action_archive')
        self.assertEqual(matched, first)
        self.assertNotEqual(matched, second)

    def test_no_rule_means_no_approval(self):
        partner = self._make_partner()
        self.assertFalse(
            self.env['approval.rule']._match(partner, 'action_archive'))

    # ------------------------------------------------------------------
    # Reading the document
    # ------------------------------------------------------------------
    def test_requester_defaults_to_creator(self):
        rule = self._make_rule()
        partner = self._make_partner().with_user(self.requester)
        partner_as_requester = self.env['res.partner'].with_user(
            self.requester).create({'name': 'Created by Ray'})
        self.assertEqual(rule._get_requester(partner_as_requester),
                         self.requester)
        self.assertEqual(rule._get_requester(partner), self.env.user)

    def test_requester_from_configured_field(self):
        rule = self._make_rule(
            requester_field_id=self.env['ir.model.fields']._get(
                'res.partner', 'user_id').id)
        partner = self._make_partner(user_id=self.requester.id)
        self.assertEqual(rule._get_requester(partner), self.requester)

    def test_amount_missing_field_is_zero(self):
        rule = self._make_rule()
        self.assertEqual(rule._get_amount(self._make_partner()), 0.0)

    # ------------------------------------------------------------------
    # Approver resolution
    # ------------------------------------------------------------------
    def test_approvers_from_group(self):
        group = self.env['res.groups'].create({'name': 'Approval Test Group'})
        group.user_ids = [(4, self.approver.id)]
        rule = self._make_rule(step_ids=[(0, 0, {
            'name': 'Group step', 'approver_type': 'group',
            'group_id': group.id})])
        approvers = rule.step_ids._resolve_approvers(self._make_partner())
        self.assertIn(self.approver, approvers)

    def test_approvers_from_document_field(self):
        rule = self._make_rule(step_ids=[(0, 0, {
            'name': 'Salesperson', 'approver_type': 'field',
            'approver_field_id': self.env['ir.model.fields']._get(
                'res.partner', 'user_id').id})])
        partner = self._make_partner(user_id=self.approver.id)
        self.assertEqual(rule.step_ids._resolve_approvers(partner),
                         self.approver)

    def test_approvers_from_org_chart(self):
        manager_user = self.env['res.users'].create({
            'name': 'Boss', 'login': 'approval_boss',
            'group_ids': self.user_groups})
        manager = self.env['hr.employee'].create({
            'name': 'Boss', 'user_id': manager_user.id})
        self.env['hr.employee'].create({
            'name': 'Ray', 'user_id': self.requester.id,
            'parent_id': manager.id})
        rule = self._make_rule(
            requester_field_id=self.env['ir.model.fields']._get(
                'res.partner', 'user_id').id,
            step_ids=[(0, 0, {'name': 'Manager', 'approver_type': 'manager'})])
        partner = self._make_partner(user_id=self.requester.id)
        self.assertEqual(rule.step_ids._resolve_approvers(partner),
                         manager_user)

    # ------------------------------------------------------------------
    # Step semantics
    # ------------------------------------------------------------------
    def test_steps_are_sequential(self):
        other = self.env['res.users'].create({
            'name': 'Second Approver', 'login': 'approval_second',
            'group_ids': self.user_groups})
        rule = self._make_rule(step_ids=[
            (0, 0, {'sequence': 1, 'name': 'One', 'approver_type': 'users',
                    'user_ids': [(6, 0, self.approver.ids)]}),
            (0, 0, {'sequence': 2, 'name': 'Two', 'approver_type': 'users',
                    'user_ids': [(6, 0, other.ids)]}),
        ])
        partner = self._make_partner()
        request = self.env['approval.request']._request_approval(
            partner, 'action_archive', rule)
        steps = request.step_ids.sorted('sequence')
        self.assertTrue(steps[0].with_user(self.approver).can_approve)
        self.assertFalse(steps[1].with_user(other).can_approve,
                         "Step 2 cannot be approved before step 1")
        steps[0].with_user(self.approver).action_approve_step()
        self.assertEqual(request.state, 'pending')
        self.assertTrue(steps[1].with_user(other).can_approve)

    def test_mode_all_requires_everyone(self):
        other = self.env['res.users'].create({
            'name': 'Other', 'login': 'approval_other',
            'group_ids': self.user_groups})
        rule = self._make_rule(step_ids=[(0, 0, {
            'name': 'Both', 'approver_type': 'users', 'approval_mode': 'all',
            'user_ids': [(6, 0, (self.approver | other).ids)]})])
        request = self.env['approval.request']._request_approval(
            self._make_partner(), 'action_archive', rule)
        step = request.step_ids
        step.with_user(self.approver).action_approve_step()
        self.assertEqual(step.status, 'pending', "One approval is not enough")
        step.with_user(other).action_approve_step()
        self.assertEqual(step.status, 'approved')

    def test_approver_cannot_approve_twice(self):
        other = self.env['res.users'].create({
            'name': 'Other', 'login': 'approval_twice',
            'group_ids': self.user_groups})
        rule = self._make_rule(step_ids=[(0, 0, {
            'name': 'Both', 'approver_type': 'users', 'approval_mode': 'all',
            'user_ids': [(6, 0, (self.approver | other).ids)]})])
        request = self.env['approval.request']._request_approval(
            self._make_partner(), 'action_archive', rule)
        request.step_ids.with_user(self.approver).action_approve_step()
        self.assertFalse(
            request.step_ids.with_user(self.approver).can_approve)

    def test_auto_approval_all_scope(self):
        rule = self._make_rule(
            amount_field_id=self.env['ir.model.fields']._get(
                'res.partner', 'credit_limit').id,
            auto_ids=[(0, 0, {'name': 'small', 'max_amount': 100.0,
                              'scope': 'all'})])
        request = self.env['approval.request']._request_approval(
            self._make_partner(credit_limit=10.0), 'action_archive', rule)
        self.assertEqual(request.state, 'approved')

    def test_auto_approval_first_scope(self):
        other = self.env['res.users'].create({
            'name': 'Other', 'login': 'approval_first_scope',
            'group_ids': self.user_groups})
        rule = self._make_rule(
            amount_field_id=self.env['ir.model.fields']._get(
                'res.partner', 'credit_limit').id,
            step_ids=[
                (0, 0, {'sequence': 1, 'name': 'One', 'approver_type': 'users',
                        'user_ids': [(6, 0, self.approver.ids)]}),
                (0, 0, {'sequence': 2, 'name': 'Two', 'approver_type': 'users',
                        'user_ids': [(6, 0, other.ids)]}),
            ],
            auto_ids=[(0, 0, {'name': 'small', 'max_amount': 100.0,
                              'scope': 'first'})])
        request = self.env['approval.request']._request_approval(
            self._make_partner(credit_limit=10.0), 'action_archive', rule)
        self.assertEqual(request.state, 'pending')
        steps = request.step_ids.sorted('sequence')
        self.assertEqual(steps[0].status, 'approved')
        self.assertEqual(steps[1].status, 'pending')

    def test_reject_marks_step_and_request(self):
        rule = self._make_rule()
        request = self.env['approval.request']._request_approval(
            self._make_partner(), 'action_archive', rule)
        self.env['approval.reject.wizard'].with_user(self.approver).create({
            'request_id': request.id,
            'step_id': request.current_step_id.id,
            'reason': 'Not now',
        }).action_confirm()
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.reject_reason, 'Not now')
        self.assertEqual(request.step_ids.status, 'rejected')

    def test_banner_payload(self):
        rule = self._make_rule()
        partner = self._make_partner()
        self.env['approval.request']._request_approval(
            partner, 'action_archive', rule)
        data = self.env['approval.request'].with_user(
            self.approver).approval_banner_data('res.partner', partner.id)
        self.assertTrue(data['enabled'])
        self.assertEqual(data['state'], 'pending')
        self.assertTrue(data['can_approve'])
        self.assertEqual(len(data['steps']), 1)
        self.assertTrue(data['steps'][0]['is_current'])

    def test_banner_payload_without_rule(self):
        partner = self._make_partner()
        self.assertFalse(
            self.env['approval.request'].approval_banner_data(
                'res.partner', partner.id)['enabled'])

    # ------------------------------------------------------------------
    # Configuration guards
    # ------------------------------------------------------------------
    def test_unknown_method_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_rule(method_name='action_does_not_exist')

    def test_crud_method_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_rule(method_name='write')

    def test_private_method_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_rule(method_name='_compute_display_name')
