# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import fields, models


class ResourceResource(models.Model):
    _inherit = 'resource.resource'

    employee_skill_ids = fields.One2many(related='employee_id.employee_skill_ids')
