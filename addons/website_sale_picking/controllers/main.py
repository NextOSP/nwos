# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import _
from nwos.exceptions import ValidationError
from nwos.http import request

from nwos.addons.website_sale.controllers.main import WebsiteSale
from nwos.addons.website_sale.controllers.payment import PaymentPortal


class PaymentPortalOnsite(PaymentPortal):

    def _validate_transaction_for_order(self, transaction, sale_order):
        """
        Throws a ValidationError if the user tries to pay on site without also using an onsite delivery carrier
        Also sets the sale order's warehouse id to the carrier's if it exists
        """
        super()._validate_transaction_for_order(transaction, sale_order)
        sale_order = sale_order.exists().sudo()

        # This should never be triggered unless the user intentionally forges a request.
        if sale_order.carrier_id.delivery_type != 'onsite' and (
            transaction.provider_id.code == 'custom'
            and transaction.provider_id.custom_mode == 'onsite'
        ):
            raise ValidationError(_("You cannot pay onsite if the delivery is not onsite"))

        if sale_order.carrier_id.delivery_type == 'onsite' and sale_order.carrier_id.warehouse_id:
            sale_order.warehouse_id = sale_order.carrier_id.warehouse_id


class WebsiteSalePicking(WebsiteSale):

    def _check_shipping_partner_mandatory_fields(self, partner_id):
        order_sudo = request.website.sale_get_order()
        carrier_sudo = order_sudo.carrier_id
        if carrier_sudo.delivery_type == 'onsite' and partner_id == carrier_sudo.warehouse_id.partner_id:
            return True

        return super()._check_shipping_partner_mandatory_fields(partner_id)
