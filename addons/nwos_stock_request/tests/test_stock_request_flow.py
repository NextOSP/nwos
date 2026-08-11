# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos.exceptions import UserError
from nwos.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockRequestFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.approver = cls.env['res.users'].create({
            'name': 'Approver', 'login': 'sr_approver',
            'group_ids': [(4, cls.env.ref(
                'nwos_stock_request.group_stock_request_approver').id)]})
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Test Vendor', 'is_company': True})
        cls.product = cls.env['product.product'].create({
            'name': 'Test Item',
            'type': 'consu',
            'purchase_ok': True,
            'seller_ids': [(0, 0, {'partner_id': cls.vendor.id, 'price': 10.0})],
        })

    def _approval(self, request):
        return self.env['approval.request'].search([
            ('res_model', '=', 'stock.request'),
            ('res_id', '=', request.id),
        ], order='id desc', limit=1)

    def _new_request(self):
        return self.env['stock.request'].create({
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'product_qty': 5.0,
                'product_uom': self.product.uom_id.id,
                'price_unit': 10.0,
            })],
        })

    def test_sequence_assigned(self):
        req = self._new_request()
        self.assertNotEqual(req.name, 'New')
        self.assertTrue(req.name.startswith('SR/'))

    def test_estimated_total(self):
        req = self._new_request()
        self.assertEqual(req.estimated_total, 50.0)

    def test_submit_approve_generates_purchase(self):
        req = self._new_request()
        req.action_submit()
        self.assertEqual(req.state, 'to_approve')
        req.with_user(self.approver).action_approve()
        self.assertEqual(req.state, 'approved')
        req.action_generate_purchase()
        self.assertEqual(req.state, 'done')
        self.assertEqual(len(req.purchase_order_ids), 1,
                         "A purchase order should be linked to the request")
        self.assertEqual(req.purchase_order_ids.partner_id, self.vendor)
        self.assertEqual(req.purchase_order_ids.stock_request_id, req)

    def test_generate_purchase_is_idempotent(self):
        """A second click never duplicates what was already sourced."""
        req = self._new_request()
        req.action_submit()
        req.with_user(self.approver).action_approve()
        req.action_generate_purchase()
        self.assertTrue(all(req.line_ids.mapped('is_sourced')))
        self.assertEqual(req.pending_source_count, 0,
                         "Nothing left to source -> the button is hidden")
        with self.assertRaises(UserError):
            req.action_generate_purchase()
        self.assertEqual(len(req.purchase_order_ids), 1)

    def test_replenish_line_is_traced_back(self):
        """A Replenish line links its procurement results back to the request."""
        self.product.route_ids = [
            (6, 0, self.env.ref('purchase_stock.route_warehouse0_buy').ids)]
        req = self._new_request()
        req.line_ids.source_action = 'replenish'
        req.action_submit()
        req.with_user(self.approver).action_approve()
        req.action_generate_purchase()
        self.assertEqual(req.state, 'done')
        self.assertTrue(req.stock_reference_id,
                        "Replenishment must be tied to a stock reference")
        # The Buy route turned the procurement into a PO: it belongs to the request
        self.assertEqual(len(req.purchase_order_ids), 1)
        self.assertEqual(req.purchase_order_ids.stock_request_id, req)
        self.assertEqual(req.pending_source_count, 0)

    def test_fulfillment_lifecycle(self):
        """Delivery/payment status tracks the linked PO lifecycle."""
        req = self._new_request()
        req.action_submit()
        req.with_user(self.approver).action_approve()
        req.action_generate_purchase()
        po = req.purchase_order_ids
        self.assertTrue(po)
        self.assertEqual(req.fulfillment_state, 'rfq')      # PO still a draft RFQ
        self.assertEqual(req.payment_state, 'no_bill')
        po.button_confirm()                                  # -> Purchase Order
        self.assertIn(req.fulfillment_state, ('ordered', 'waiting'))

    def test_generate_purchase_requires_vendor(self):
        """A Purchase line without a vendor blocks generation with a clear error."""
        product = self.env['product.product'].create({
            'name': 'No-vendor item', 'type': 'consu', 'purchase_ok': True})
        req = self.env['stock.request'].create({
            'line_ids': [(0, 0, {
                'product_id': product.id, 'name': product.name,
                'product_qty': 3.0, 'price_unit': 5.0})]})
        req.action_submit()
        req.with_user(self.approver).action_approve()
        with self.assertRaises(Exception):
            req.action_generate_purchase()

    def test_refuse_flow(self):
        req = self._new_request()
        req.action_submit()
        wizard = self.env['stock.request.refuse'].create({
            'request_id': req.id, 'reason': 'Not needed'})
        wizard.action_confirm()
        self.assertEqual(req.state, 'refused')
        self.assertEqual(req.refuse_reason, 'Not needed')
        self.assertEqual(self._approval(req).state, 'cancel')

    def test_refuse_from_the_approval_banner(self):
        """Refusing through the framework wizard drives the request state."""
        req = self._new_request()
        req.action_submit()
        approval = self._approval(req)
        self.env['approval.reject.wizard'].with_user(self.approver).create({
            'request_id': approval.id,
            'step_id': approval.current_step_id.id,
            'reason': 'Budget frozen',
        }).action_confirm()
        self.assertEqual(approval.state, 'rejected')
        self.assertEqual(req.state, 'refused')
        self.assertEqual(req.refuse_reason, 'Budget frozen')

    def test_reset_to_draft_cancels_the_approval(self):
        req = self._new_request()
        req.action_submit()
        approval = self._approval(req)
        req.action_reset_to_draft()
        self.assertEqual(req.state, 'draft')
        self.assertEqual(approval.state, 'cancel')

    def test_default_single_step_approval(self):
        """The shipped rule creates one step; the approver completes it."""
        req = self._new_request()
        req.action_submit()
        self.assertEqual(req.state, 'to_approve')
        approval = self._approval(req)
        self.assertEqual(approval.state, 'pending')
        self.assertEqual(len(approval.step_ids), 1)
        req.with_user(self.approver).action_approve()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self._approval(req).state, 'done')

    def test_multi_step_sequential_rule(self):
        """A 2-step rule must be approved in order before the request is approved."""
        u1 = self.env['res.users'].create({
            'name': 'Approver One', 'login': 'appr1',
            'group_ids': [(4, self.env.ref(
                'nwos_stock_request.group_stock_request_approver').id)]})
        u2 = self.env['res.users'].create({
            'name': 'Approver Two', 'login': 'appr2',
            'group_ids': [(4, self.env.ref(
                'nwos_stock_request.group_stock_request_approver').id)]})
        self.env['approval.rule'].create({
            'name': 'Two steps',
            'sequence': 1,  # wins over the rule shipped with the module
            'res_model_id': self.env['ir.model']._get('stock.request').id,
            'method_name': 'action_confirm_request',
            'reject_method_name': 'action_refuse_from_approval',
            'step_ids': [
                (0, 0, {'sequence': 1, 'name': 'Step 1',
                        'approver_type': 'users', 'user_ids': [(6, 0, u1.ids)]}),
                (0, 0, {'sequence': 2, 'name': 'Step 2',
                        'approver_type': 'users', 'user_ids': [(6, 0, u2.ids)]}),
            ],
        })
        req = self._new_request()
        req.action_submit()
        steps = self._approval(req).step_ids.sorted('sequence')
        self.assertEqual(len(steps), 2)
        # Step 2 approver cannot approve before step 1
        self.assertTrue(steps[0].with_user(u1).can_approve)
        self.assertFalse(steps[1].with_user(u2).can_approve)
        steps[0].with_user(u1).action_approve_step()
        self.assertEqual(req.state, 'to_approve')  # step 2 still pending
        steps[1].with_user(u2).action_approve_step()
        self.assertEqual(req.state, 'approved')

    def test_auto_approval_all(self):
        """An auto-approval (scope all) below the amount approves the whole request."""
        rule = self.env.ref('nwos_stock_request.approval_rule_stock_request')
        rule.write({'auto_ids': [(0, 0, {
            'name': 'Small buys', 'max_amount': 1000.0, 'scope': 'all'})]})
        req = self._new_request()  # total 50
        req.action_submit()
        self.assertEqual(req.state, 'approved')

    def test_create_product_from_spec(self):
        req = self.env['stock.request'].create({
            'line_ids': [(0, 0, {
                'name': 'Custom bracket, 10mm steel',
                'product_qty': 2.0,
            })],
        })
        line = req.line_ids
        self.assertFalse(line.product_id)
        line.action_create_product()
        self.assertTrue(line.product_id)
        self.assertEqual(line.product_id.name, 'Custom bracket, 10mm steel')
