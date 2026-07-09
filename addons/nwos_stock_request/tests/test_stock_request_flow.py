# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
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

    def test_default_single_step_approval(self):
        """No rule -> one default step, approver can approve to completion."""
        req = self._new_request()
        req.action_submit()
        self.assertEqual(req.state, 'to_approve')
        self.assertEqual(len(req.approval_ids), 1)
        req.with_user(self.approver).action_approve()
        self.assertEqual(req.state, 'approved')

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
        self.env['stock.request.approval.rule'].create({
            'name': 'Two steps',
            'min_amount': 0.0,
            'step_ids': [
                (0, 0, {'sequence': 1, 'name': 'Step 1',
                        'approver_type': 'users', 'user_ids': [(6, 0, u1.ids)]}),
                (0, 0, {'sequence': 2, 'name': 'Step 2',
                        'approver_type': 'users', 'user_ids': [(6, 0, u2.ids)]}),
            ],
        })
        req = self._new_request()
        req.action_submit()
        self.assertEqual(len(req.approval_ids), 2)
        # Step 2 approver cannot approve before step 1
        self.assertTrue(req.approval_ids.sorted('sequence')[0].with_user(u1).can_approve)
        self.assertFalse(req.approval_ids.sorted('sequence')[1].with_user(u2).can_approve)
        req.approval_ids.sorted('sequence')[0].with_user(u1).action_approve_step()
        self.assertEqual(req.state, 'to_approve')  # step 2 still pending
        req.approval_ids.sorted('sequence')[1].with_user(u2).action_approve_step()
        self.assertEqual(req.state, 'approved')

    def test_auto_approval_all(self):
        """An auto-approval (scope all) below the amount approves the whole request."""
        self.env['stock.request.approval.auto'].create({
            'name': 'Small buys', 'max_amount': 1000.0, 'scope': 'all'})
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
