# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
"""Move the built-in stock-request approval engine onto `nwos_approval`.

The legacy models are gone from the registry by the time this runs (their
Python is deleted in the same release), so the source data is read with plain
SQL. Dropping the obsolete tables happens in end-migrate.py, so a failure here
never destroys the source.
"""
import logging
from collections import defaultdict

from nwos import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

GATED_METHOD = 'action_confirm_request'
REJECT_METHOD = 'action_refuse_from_approval'


def _exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", [f'public.{table}'])
    return bool(cr.fetchone()[0])


def _rows(cr, query, params=None):
    cr.execute(query, params or [])
    columns = [d[0] for d in cr.description]
    return [dict(zip(columns, row)) for row in cr.fetchall()]


def _m2m(cr, table, source_column, target_column):
    """Read a many2many relation table as {source_id: [target_id, ...]}."""
    result = defaultdict(list)
    if not _exists(cr, table):
        return result
    cr.execute(f'SELECT "{source_column}", "{target_column}" FROM "{table}"')
    for source, target in cr.fetchall():
        result[source].append(target)
    return result


def _condition_domain(rule, warehouses, departments):
    """Rebuild the old typed match columns as a plain domain."""
    leaves = []
    if rule.get('purpose'):
        leaves.append(('purpose', '=', rule['purpose']))
    if warehouses:
        leaves.append(('warehouse_id', 'in', warehouses))
    if departments:
        leaves.append(('department_id', 'in', departments))
    return repr(leaves)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'approval.rule' not in env:
        _logger.error("nwos_approval is not installed; approval data not migrated")
        return
    if not _exists(cr, 'stock_request_approval_rule'):
        _logger.info("No legacy approval tables; nothing to migrate")
        return

    model = env['ir.model']._get('stock.request')
    Fields = env['ir.model.fields']
    manager_group = env.ref('nwos_stock_request.group_stock_request_manager')
    approver_group = env.ref('nwos_stock_request.group_stock_request_approver')
    template = env.ref(
        'nwos_stock_request.mail_template_stock_request_approved',
        raise_if_not_found=False)

    common = {
        'res_model_id': model.id,
        'method_name': GATED_METHOD,
        'reject_method_name': REJECT_METHOD,
        'amount_field_id': Fields._get('stock.request', 'estimated_total').id,
        'currency_field_id': Fields._get('stock.request', 'currency_id').id,
        'requester_field_id': Fields._get('stock.request', 'requester_id').id,
        'department_field_id': Fields._get('stock.request', 'department_id').id,
        'override_group_id': manager_group.id,
        'mail_template_id': template.id if template else False,
    }

    # --- auto-approval: legacy rows were global, they become per-rule lines
    autos = []
    if _exists(cr, 'stock_request_approval_auto'):
        auto_users = _m2m(
            cr, 'res_users_stock_request_approval_auto_rel',
            'stock_request_approval_auto_id', 'res_users_id')
        for auto in _rows(cr, """
                SELECT id, name, sequence, max_amount, scope
                FROM stock_request_approval_auto WHERE active IS NOT FALSE
                ORDER BY sequence, id"""):
            autos.append({
                'name': auto['name'] or 'Auto-approval',
                'sequence': auto['sequence'] or 10,
                'user_ids': [(6, 0, auto_users.get(auto['id'], []))],
                'max_amount': auto['max_amount'] or 0.0,
                'scope': auto['scope'] or 'all',
            })
    threshold = float(env['ir.config_parameter'].get_param(
        'nwos_stock_request.approval_amount', 0.0) or 0.0)
    if threshold:
        autos.append({
            'name': 'Below approval amount',
            'sequence': 99,
            'max_amount': threshold,
            'scope': 'all',
        })

    # --- rules + steps ----------------------------------------------------
    rule_warehouses = _m2m(
        cr, 'stock_request_approval_rule_stock_warehouse_rel',
        'stock_request_approval_rule_id', 'stock_warehouse_id')
    rule_departments = _m2m(
        cr, 'hr_department_stock_request_approval_rule_rel',
        'stock_request_approval_rule_id', 'hr_department_id')
    step_users = _m2m(
        cr, 'res_users_stock_request_approval_rule_step_rel',
        'stock_request_approval_rule_step_id', 'res_users_id')

    steps_by_rule = defaultdict(list)
    if _exists(cr, 'stock_request_approval_rule_step'):
        for step in _rows(cr, """
                SELECT id, rule_id, sequence, name, approver_type, group_id,
                       manager_level, approval_mode
                FROM stock_request_approval_rule_step ORDER BY sequence, id"""):
            steps_by_rule[step['rule_id']].append((0, 0, {
                'sequence': step['sequence'] or 10,
                'name': step['name'] or 'Approval',
                'approver_type': step['approver_type'] or 'group',
                'user_ids': [(6, 0, step_users.get(step['id'], []))],
                'group_id': step['group_id'],
                'manager_level': step['manager_level'] or 1,
                'approval_mode': step['approval_mode'] or 'any',
            }))

    rule_map = {}
    legacy_rules = _rows(cr, """
        SELECT id, name, sequence, active, company_id, min_amount, max_amount,
               purpose
        FROM stock_request_approval_rule ORDER BY sequence, id""")
    for rule in legacy_rules:
        rule_map[rule['id']] = env['approval.rule'].create(dict(common, **{
            'name': rule['name'] or 'Stock Request Approval',
            'sequence': rule['sequence'] or 10,
            'active': rule['active'] is not False,
            'company_id': rule['company_id'],
            'condition_domain': _condition_domain(
                rule, rule_warehouses.get(rule['id']),
                rule_departments.get(rule['id'])),
            'amount_min': rule['min_amount'] or 0.0,
            'amount_max': rule['max_amount'] or 0.0,
            'step_ids': steps_by_rule.get(rule['id'], []),
            'auto_ids': [(0, 0, dict(auto)) for auto in autos],
        }))

    if not legacy_rules:
        # No custom rule existed: the module already ships an equivalent
        # single-step rule, so just carry the auto-approval lines over to it.
        shipped = env.ref('nwos_stock_request.approval_rule_stock_request',
                          raise_if_not_found=False)
        if not shipped:
            shipped = env['approval.rule'].create(dict(common, **{
                'name': 'Stock Request Approval',
                'sequence': 50,
                'condition_domain': '[]',
                'step_ids': [(0, 0, {
                    'sequence': 10,
                    'name': 'Approval',
                    'approver_type': 'group',
                    'group_id': approver_group.id,
                    'approval_mode': 'any',
                })],
            }))
        if autos:
            shipped.write({'auto_ids': [(0, 0, dict(auto)) for auto in autos]})
        rule_map[None] = shipped

    # --- live requests still waiting for approval -------------------------
    default_rule = rule_map.get(None) or (
        list(rule_map.values())[0] if rule_map else None)
    candidates = _m2m(cr, 'stock_request_approval_candidate_rel',
                      'approval_id', 'user_id')
    approved = _m2m(cr, 'stock_request_approval_done_rel',
                    'approval_id', 'user_id')
    live_steps = defaultdict(list)
    if _exists(cr, 'stock_request_approval'):
        for step in _rows(cr, """
                SELECT id, request_id, sequence, name, approval_mode, status,
                       reject_reason
                FROM stock_request_approval ORDER BY sequence, id"""):
            live_steps[step['request_id']].append(step)

    pending = _rows(cr, """
        SELECT id, company_id, requester_id, currency_id, estimated_total,
               approval_rule_id
        FROM stock_request WHERE state = 'to_approve'""")
    Request = env['approval.request']
    Step = env['approval.step']
    for request in pending:
        rule = rule_map.get(request.get('approval_rule_id')) or default_rule
        document = env['stock.request'].browse(request['id'])
        new_request = Request.create({
            'rule_id': rule.id if rule else False,
            'company_id': request['company_id'],
            'res_model': 'stock.request',
            'res_id': request['id'],
            'res_name': document.display_name,
            'method_name': GATED_METHOD,
            'requester_id': request['requester_id'],
            'amount': request['estimated_total'] or 0.0,
            'currency_id': request['currency_id'],
            'override_group_id': manager_group.id,
        })
        for step in live_steps.get(request['id'], []):
            Step.create({
                'request_id': new_request.id,
                'sequence': step['sequence'] or 10,
                'name': step['name'] or 'Approval',
                'approval_mode': step['approval_mode'] or 'any',
                'approver_ids': [(6, 0, candidates.get(step['id'], []))],
                'approved_user_ids': [(6, 0, approved.get(step['id'], []))],
                'status': step['status'] or 'pending',
                'reject_reason': step['reject_reason'],
            })

    env['ir.config_parameter'].set_param(
        'nwos_stock_request.approval_amount', '')
    _logger.info(
        "Migrated %s approval rule(s) and %s pending request(s) to nwos_approval",
        len(rule_map), len(pending))
