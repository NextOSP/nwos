# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from lxml import etree

from nwos import models
from nwos.tests.common import TransactionCase


class TestStreetFields(TransactionCase):

    def test_city_fields_filter_by_selected_state(self):
        for xmlid in (
            'base_address_extended.address_street_extended_form',
            'base_address_extended.address_street_extended_city_form',
        ):
            arch = etree.fromstring(self.env.ref(xmlid).arch_db.encode())
            city_fields = arch.xpath("//field[@name='city_id']")
            self.assertTrue(city_fields)
            for city_field in city_fields:
                self.assertIn("('state_id', '=?', state_id)", city_field.get('domain'))

    def test_partner_create(self):
        """ Will test the compute and inverse methods of street fields when creating partner records. """
        mx_id = self.env.ref('base.mx').id
        partner = self.env['res.partner'].create({'name': 'Test Address', 'country_id': mx_id})

        values = [
            ['', '', '', ''],
            ['Place Royale', 'Place Royale', '', ''],
            ['Chaussee de Namur 40a - 2b', 'Chaussee de Namur', '40a', '2b'],
            ['Chaussee de Namur 1', 'Chaussee de Namur', '1', ''],
            ['40 Chaussee de Namur', '40 Chaussee de Namur', '', ''],
            ['Chaussee de Namur, 40 - Apt 2b', 'Chaussee de Namur,', '40', 'Apt 2b'],
            ['header Chaussee de Namur, 40 trailer ', 'header Chaussee de Namur, 40 trailer', '', ''],
            ['\nCl 53\n # 43 - 81', 'Cl 53\n #', '43', '81'],
            ['Street Line 1\nNumber Line 2 44 76', 'Street Line 1\nNumber Line 2 44', '76', ''],
        ]

        for street, name, number, number2 in values:
            # test street -> street values (compute)
            partner.street = street
            self.assertEqual(partner.street_name, name, 'Wrongly formatted street name: expected %s, received %s' % (name, partner.street_name))
            self.assertEqual(partner.street_number, number, 'Wrongly formatted street number: expected %s, received %s' % (number, partner.street_number))
            self.assertEqual(partner.street_number2, number2, 'Wrongly formatted street number2: expected %s, received %s' % (number2, partner.street_number2))

        for street, name, number, number2 in values:
            partner.street_number2 = number2
            partner.street_number = number
            partner.street_name = name
            self.assertEqual(partner.street, street.strip(), 'Wrongly formatted street: expected %s, received %s' % (street, partner.street))

    def test_child_sync(self):
        """ Test that city_id is propagated to (contact-type) children contacts. """
        usa = self.env.ref('base.us')
        new_york_city = self.env['res.city'].create({
            'name': 'New York',
            'country_id': usa.id,
        })
        parent = self.env['res.partner'].create({
            'name': 'Parent Company',
            'country_id': usa.id,
            'city_id': new_york_city.id,
        })
        child = self.env['res.partner'].create({
            'name': 'Child Contact',
            'type': 'contact',
            'parent_id': parent.id,
        })
        self.assertRecordValues(child, [{
            'name': 'Child Contact',
            'country_id': usa.id,
            'city_id': new_york_city.id,
        }])

    def test_city_display_name_can_include_state(self):
        usa = self.env.ref('base.us')
        california = self.env.ref('base.state_us_5')
        city = self.env['res.city'].create({
            'name': 'Springfield',
            'zipcode': '90210',
            'country_id': usa.id,
            'state_id': california.id,
        })

        self.assertEqual(city.display_name, 'Springfield (90210)')
        self.assertEqual(
            city.with_context(show_state_name=True).display_name,
            'Springfield (90210), California',
        )

    def test_changing_state_clears_incompatible_city(self):
        usa = self.env.ref('base.us')
        california = self.env.ref('base.state_us_5')
        maryland = self.env.ref('base.state_us_33')
        city = self.env['res.city'].create({
            'name': 'Springfield',
            'zipcode': '90210',
            'country_id': usa.id,
            'state_id': california.id,
        })
        partner = self.env['res.partner'].new({
            'name': 'Test Address',
            'country_id': usa.id,
            'state_id': california.id,
            'city_id': city.id,
            'city': city.name,
            'zip': city.zipcode,
        })

        partner.state_id = maryland
        partner._onchange_state_id()

        self.assertFalse(partner.city_id)
        self.assertFalse(partner.city)
        self.assertFalse(partner.zip)

    def test_city_lookup_uses_state_to_disambiguate_duplicate_names(self):
        usa = self.env.ref('base.us')
        california = self.env.ref('base.state_us_5')
        maryland = self.env.ref('base.state_us_33')
        cities = self.env['res.city'].create([
            {
                'name': 'Springfield',
                'country_id': usa.id,
                'state_id': california.id,
            },
            {
                'name': 'Springfield',
                'country_id': usa.id,
                'state_id': maryland.id,
            },
        ])

        city = self.env['res.partner']._get_res_city_by_name(
            'Springfield', usa.id, state_id=maryland.id,
        )

        self.assertEqual(city, cities[1])
