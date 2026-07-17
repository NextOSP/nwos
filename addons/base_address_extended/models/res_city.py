# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, fields, models


class ResCity(models.Model):
    _name = 'res.city'
    _description = 'City'
    _order = 'name'
    _rec_names_search = ['name', 'zipcode']

    name = fields.Char("Name", required=True, translate=True)
    zipcode = fields.Char("Zip")
    country_id = fields.Many2one(comodel_name='res.country', string='Country', required=True)
    state_id = fields.Many2one(comodel_name='res.country.state', string='State', domain="[('country_id', '=', country_id)]")

    @api.depends('name', 'zipcode', 'state_id.name')
    @api.depends_context('show_state_name')
    def _compute_display_name(self):
        for city in self:
            name = city.name if not city.zipcode else f'{city.name} ({city.zipcode})'
            if self.env.context.get('show_state_name') and city.state_id:
                name = f'{name}, {city.state_id.name}'
            city.display_name = name
