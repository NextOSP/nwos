# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        return False

    @api.model
    def _load_pos_self_data_read(self, records, config):
        """ Read specific fields from the given records """
        fields = ['id', 'name', 'write_date', 'property_product_pricelist']
        records = records.read(fields, load=False)
        return records or []
