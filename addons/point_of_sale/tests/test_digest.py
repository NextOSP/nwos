# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.addons.digest.tests.common import TestDigestCommon
from nwos.addons.point_of_sale.tests.common import CommonPosTest
from nwos.tools import mute_logger
from nwos.tests import tagged


@tagged('post_install', '-at_install')
class TestAccountDigest(TestDigestCommon, CommonPosTest):

    @classmethod
    @mute_logger('nwos.models.unlink')
    def setUpClass(cls):
        super().setUpClass()

    def test_kpi_invoiced_pos_orders_counted(self):
        order_data = {
            'line_data': [
                {'product_id': self.ten_dollars_with_10_incl.product_variant_id.id},
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id, 'amount': 10},
            ],
        }

        self.pos_config_usd.open_ui()
        current_session = self.pos_config_usd.current_session_id

        self.create_backend_pos_order({**order_data, 'order_data': {'to_invoice': False, 'partner_id': False}})
        self.create_backend_pos_order({**order_data, 'order_data': {'to_invoice': True, 'partner_id': self.partner.id}})
        current_session.close_session_from_ui()

        self.assertEqual(self.digest_1.kpi_pos_total_value, 20.0)
