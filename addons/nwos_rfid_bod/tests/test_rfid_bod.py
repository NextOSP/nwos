from nwos.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRfidBod(TransactionCase):

    def test_dashboard_data_contains_rfid_kpis(self):
        data = self.env['bod.dashboard'].get_dashboard_data(period='month')
        self.assertIn('rfid', data['sections'])
        self.assertIn('active_sites', data['rfid'])
        self.assertIn('mrr', data['rfid'])
        self.assertIn('on_time_delivery_pct', data['rfid'])

    def test_monthly_report_html_renders(self):
        html, _report_type = self.env['ir.actions.report']._render_qweb_html(
            'nwos_rfid_bod.action_report_rfid_bod_monthly', self.env.company.ids)
        self.assertIn(b'Nextwaves Kit', html)
