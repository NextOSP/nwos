# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.tests import tagged
from nwos.tools import mute_logger

from nwos.addons.delivery.tests.cash_on_delivery_common import CashOnDeliveryCommon


@tagged('post_install', '-at_install')
class TestCODPaymentTransaction(CashOnDeliveryCommon):

    def test_choosing_cod_payment_confirms_order(self):
        order = self.sale_order
        self.free_delivery.allow_cash_on_delivery = True
        order.carrier_id = self.free_delivery
        tx = self._create_transaction(
            flow='direct',
            sale_order_ids=[order.id],
            state='pending',
            provider_id=self.cod_provider.id,
            payment_method_id=self.cod_provider.payment_method_ids.id,
        )
        with mute_logger('nwos.addons.sale.models.payment_transaction'):
            tx._post_process()

        self.assertEqual(order.state, 'sale')
