from datetime import timedelta

from nwos import Command, fields
from nwos.exceptions import UserError
from nwos.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNextwavesKit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create({'name': 'Kit Customer'})
        cls.site_address = cls.env['res.partner'].create({
            'name': 'Kit Customer - Factory A',
            'parent_id': cls.customer.id,
            'type': 'delivery',
            'street': '1 Test Road',
        })
        cls.standard_product = cls.env['product.product'].create({
            'name': 'RFID Tag Roll',
            'type': 'consu',
            'is_storable': True,
            'list_price': 100,
        })
        cls.reader = cls.env['product.product'].create({
            'name': 'RFID Reader',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'serial',
            'list_price': 1200,
        })
        cls.antenna = cls.env['product.product'].create({
            'name': 'RFID Antenna',
            'type': 'consu',
            'is_storable': True,
            'list_price': 300,
        })
        cls.subscription_product = cls.env['product.product'].create({
            'name': 'RFID Cloud Monthly',
            'type': 'service',
            'rfid_offer_type': 'subscription',
            'rfid_billing_interval_months': '1',
            'list_price': 50,
        })
        cls.income_account = cls.env['account.account'].create({
            'name': 'Kit Service Revenue',
            'code': 'KIT.REV',
            'account_type': 'income',
            'company_ids': [Command.link(cls.env.company.id)],
        })
        cls.receivable_account = cls.env['account.account'].create({
            'name': 'Kit Customer Receivable',
            'code': 'KIT.REC',
            'account_type': 'asset_receivable',
            'reconcile': True,
            'company_ids': [Command.link(cls.env.company.id)],
        })
        cls.customer.property_account_receivable_id = cls.receivable_account
        cls.subscription_product.property_account_income_id = cls.income_account
        cls.env['account.journal'].create({
            'name': 'Kit Sales Journal',
            'code': 'KIT',
            'type': 'sale',
            'company_id': cls.env.company.id,
        })

    def _managed_order(self):
        order = self.env['sale.order'].create({'partner_id': self.customer.id})
        now = fields.Datetime.now()
        site = self.env['rfid.service.site'].create({
            'site_name': 'Factory A',
            'partner_id': self.customer.id,
            'installation_address_id': self.site_address.id,
            'sale_order_id': order.id,
            'planned_delivery_date': now + timedelta(days=5),
            'planned_installation_date': now + timedelta(days=7),
        })
        for product in (self.reader, self.antenna):
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': 1,
                'rfid_line_role': 'starter_kit',
                'rfid_site_id': site.id,
            })
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.subscription_product.id,
            'product_uom_qty': 1,
            'rfid_line_role': 'subscription',
            'rfid_site_id': site.id,
        })
        return order, site

    def test_ordinary_material_uses_standard_flow(self):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.standard_product.id,
                'product_uom_qty': 10,
                'rfid_line_role': 'standard',
            })],
        })
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertFalse(order.rfid_site_ids)
        self.assertTrue(order.picking_ids)
        self.assertFalse(order.picking_ids.rfid_site_id)

    def test_kit_items_require_a_sales_order_site(self):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.reader.id,
                'product_uom_qty': 1,
                'rfid_line_role': 'starter_kit',
            })],
        })
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_inline_site_uses_sales_order_customer(self):
        order = self.env['sale.order'].create({'partner_id': self.customer.id})
        now = fields.Datetime.now()

        order.write({
            'rfid_site_ids': [Command.create({
                'site_name': 'Factory A',
                'installation_address_id': self.site_address.id,
                'planned_delivery_date': now + timedelta(days=5),
                'planned_installation_date': now + timedelta(days=7),
            })],
        })

        self.assertEqual(order.rfid_site_ids.partner_id, self.customer)

    def test_selected_kit_items_create_project_delivery_and_subscription(self):
        order, site = self._managed_order()
        order.action_confirm()

        self.assertEqual(site.state, 'awaiting_payment')
        self.assertTrue(site.payment_blocked)
        self.assertEqual(site.kit_product_ids, self.reader | self.antenna)
        self.assertTrue(site.installation_project_id)
        self.assertEqual(
            set(site.installation_project_id.task_ids.mapped('rfid_task_kind')),
            {'delivery', 'installation', 'configuration', 'commissioning', 'training', 'acceptance'},
        )
        self.assertEqual(len(site.subscription_ids), 1)
        self.assertEqual(site.subscription_ids.state, 'pending')
        self.assertTrue(site.picking_ids)
        self.assertEqual(site.picking_ids.rfid_site_id, site)
        self.assertEqual(site.picking_ids.partner_id, self.site_address)

        with self.assertRaises(UserError):
            site.picking_ids.button_validate()

    def test_payment_requirement_can_be_disabled(self):
        self.env.company.rfid_require_payment_before_delivery = False
        order, site = self._managed_order()
        order.action_confirm()

        self.assertEqual(site.state, 'ready')
        self.assertTrue(site.payment_released)
        self.assertFalse(site.payment_blocked)
        delivery_tasks = site.installation_project_id.task_ids.filtered(
            lambda task: task.rfid_task_kind == 'delivery')
        self.assertTrue(delivery_tasks)
        self.assertTrue(all(
            task.state == '01_in_progress' for task in delivery_tasks))

    def test_disabling_payment_requirement_releases_waiting_sites(self):
        order, site = self._managed_order()
        order.action_confirm()
        self.assertEqual(site.state, 'awaiting_payment')
        self.assertTrue(site.payment_blocked)

        settings = self.env['res.config.settings'].create({
            'company_id': self.env.company.id,
            'rfid_require_payment_before_delivery': False,
        })
        settings.execute()

        self.assertEqual(site.state, 'ready')
        self.assertTrue(site.payment_released)
        self.assertFalse(site.payment_blocked)

    def test_kit_product_selects_project_template_and_copies_checklist(self):
        template = self.env['project.project'].create({
            'name': 'Reader Deployment Template',
            'is_template': True,
            'company_id': self.env.company.id,
        })
        self.env['project.task'].create({
            'name': 'Lên kế hoạch',
            'project_id': template.id,
            'description': (
                '<h3>Checklist</h3><ul class="o_checklist">'
                '<li>Confirm power and network</li></ul>'
            ),
        })
        self.reader.product_tmpl_id.write({
            'rfid_offer_type': 'starter_kit',
            'rfid_project_template_id': template.id,
        })

        order, site = self._managed_order()
        self.assertEqual(site.project_template_id, template)
        order.action_confirm()

        planning_task = site.installation_project_id.task_ids.filtered(
            lambda task: task.name == 'Lên kế hoạch')
        self.assertEqual(len(planning_task), 1)
        self.assertIn('Confirm power and network', planning_task.description)

    def test_conflicting_kit_templates_require_site_selection(self):
        reader_template = self.env['project.project'].create({
            'name': 'Reader Template', 'is_template': True,
            'company_id': self.env.company.id,
        })
        antenna_template = self.env['project.project'].create({
            'name': 'Antenna Template', 'is_template': True,
            'company_id': self.env.company.id,
        })
        self.reader.product_tmpl_id.write({
            'rfid_project_template_id': reader_template.id,
        })
        self.antenna.product_tmpl_id.write({
            'rfid_project_template_id': antenna_template.id,
        })

        order, site = self._managed_order()
        self.assertTrue(site.project_template_conflict)
        self.assertFalse(site.project_template_id)
        with self.assertRaises(UserError):
            order.action_confirm()

        site.project_template_id = reader_template
        self.assertTrue(site.project_template_manual)
        order.action_confirm()
        self.assertTrue(site.installation_project_id)

    def test_subscription_period_uses_prepaid_interval(self):
        order, site = self._managed_order()
        order.action_confirm()
        subscription = site.subscription_ids
        subscription.write({
            'state': 'active',
            'start_date': fields.Date.today(),
            'next_invoice_date': fields.Date.today(),
            'billing_interval_months': 6,
        })
        periods = subscription._generate_due_periods(fields.Date.today())
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods.billing_months, 6)
        self.assertEqual(periods.amount, subscription.price_unit * 6)
        periods._create_grouped_invoices()
        self.assertEqual(periods.state, 'invoiced')
        self.assertEqual(periods.invoice_id.state, 'draft')
        self.assertEqual(periods.invoice_id.invoice_line_ids.quantity, 6)
