# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nVNAddress(TransactionCase):

    def test_vietnam_two_level_address_data(self):
        vietnam = self.env.ref('base.vn')
        hanoi = self.env.ref('base.state_vn_VN-HN')
        ward = self.env.ref('l10n_vn.city_vn_00004')

        self.assertTrue(vietnam.enforce_cities)
        self.assertEqual(ward.country_id, vietnam)
        self.assertEqual(ward.state_id, hanoi)
        self.assertEqual(ward.name, 'Phường Ba Đình')
        self.assertEqual(ward.zipcode, '11120')
        self.assertEqual(
            self.env['res.city'].search_count([('country_id', '=', vietnam.id)]),
            3321,
        )
        self.assertFalse(self.env['res.city'].search([
            ('country_id', '=', vietnam.id),
            ('zipcode', 'in', (False, '')),
        ], limit=1))

    def test_vietnam_current_province_names(self):
        self.assertEqual(self.env.ref('base.state_vn_VN-26').name, 'TP Huế')
        self.assertEqual(self.env.ref('base.state_vn_VN-39').name, 'TP Đồng Nai')

    def test_selecting_ward_loads_province_and_postal_code(self):
        vietnam = self.env.ref('base.vn')
        hanoi = self.env.ref('base.state_vn_VN-HN')
        hochiminh = self.env.ref('base.state_vn_VN-SG')
        ward = self.env.ref('l10n_vn.city_vn_27094')
        partner = self.env['res.partner'].new({
            'name': 'Test Address',
            'country_id': vietnam.id,
            'state_id': hochiminh.id,
        })

        partner.city_id = ward
        partner._onchange_city_id()

        self.assertEqual(partner.city, 'Phường An Khánh')
        self.assertEqual(partner.state_id, hochiminh)
        self.assertEqual(partner.zip, '71108')

        partner.state_id = hanoi
        partner._onchange_state_id()
        self.assertFalse(partner.city_id)
        self.assertFalse(partner.city)
        self.assertFalse(partner.zip)

    def test_postal_source_anomaly_corrections(self):
        self.assertEqual(self.env.ref('l10n_vn.city_vn_11713').zipcode, '05127')
        self.assertEqual(self.env.ref('l10n_vn.city_vn_08872').zipcode, '15221')
        self.assertEqual(self.env.ref('l10n_vn.city_vn_06970').name, 'Xã Ba Chẽ')
