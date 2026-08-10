# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
"""Drop the obsolete stock-request approval models.

Kept apart from post-migrate.py on purpose: if the data copy fails, the source
tables are still there to retry from.
"""
import logging

from nwos import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OBSOLETE_MODELS = [
    'stock.request.approval',
    'stock.request.approval.rule.step',
    'stock.request.approval.rule',
    'stock.request.approval.auto',
]


def migrate(cr, version):
    if not version:
        return
    # _force_unlink (MODULE_UNINSTALL_FLAG, ir_model.py:36) lets the ORM drop
    # columns that still carry module data — exactly what these retired models
    # are.
    env = api.Environment(cr, SUPERUSER_ID, {'_force_unlink': True})
    models = env['ir.model'].search([('model', 'in', OBSOLETE_MODELS)])
    if not models:
        return
    env['ir.model.data'].search([
        '|',
        '&', ('model', '=', 'ir.model'), ('res_id', 'in', models.ids),
        '&', ('model', '=', 'ir.model.fields'),
        ('res_id', 'in', models.field_id.ids),
    ]).unlink()
    # Unlinking ir.model cascades to its fields, ACLs, views and drops the table.
    models.unlink()
    _logger.info("Removed obsolete approval models: %s", OBSOLETE_MODELS)
