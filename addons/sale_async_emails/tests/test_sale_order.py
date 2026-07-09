# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.tests import tagged

from nwos.addons.sale.tests.common import SaleCommon


@tagged('post_install', '-at_install')
class TestSaleOrder(SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.async_emails_cron = cls.env.ref('sale.send_pending_emails_cron')
        cls.confirmation_email_template = cls.sale_order._get_confirmation_template()

    def test_order_status_email_is_sent_asynchronously(self):
        """ Test that the order status email is sent asynchronously when configured. """
        self.env['ir.config_parameter'].set_param('sale.async_emails', 'True')

        self.sale_order._send_order_notification_mail(self.confirmation_email_template)
        self.assertTrue(
            self.sale_order.pending_email_template_id,
            msg="The email template should be saved on the sales order.",
        )
        self.assertTrue(
            self.env['ir.cron.trigger'].search_count([('cron_id', '=', self.async_emails_cron.id)]),
            msg="The asynchronous email sending cron should be triggered.",
        )

    def test_order_status_email_is_sent_synchronously_if_not_configured(self):
        """ Test that the order status email is sent synchronously when nothing is configured. """
        self.env['ir.config_parameter'].set_param('sale.async_emails', 'False')

        self.sale_order._send_order_notification_mail(self.confirmation_email_template)
        self.assertFalse(
            self.env['ir.cron.trigger'].search_count([('cron_id', '=', self.async_emails_cron.id)]),
            msg="The email should be sent synchronously when the system parameter is not set.",
        )

    def test_async_emails_cron_does_not_trigger_itself(self):
        """ Test that the asynchronous email sending cron does not enter an infinite loop. """
        self.env['ir.config_parameter'].set_param('sale.async_emails', 'True')
        self.sale_order.pending_email_template_id = self.confirmation_email_template

        with self.enter_registry_test_mode():
            self.async_emails_cron.method_direct_trigger()
        self.assertFalse(
            self.sale_order.pending_email_template_id,
            msg="The email template should be removed from the sales order.",
        )
        self.assertFalse(
            self.env['ir.cron.trigger'].search_count([('cron_id', '=', self.async_emails_cron.id)]),
            msg="The email should be sent synchronously when requested by the cron.",
        )
