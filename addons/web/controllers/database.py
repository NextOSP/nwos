# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import base64
import datetime
import json
import logging
import math
import os
import re
import tempfile

from lxml import etree, html

import nwos
import nwos.modules.registry
from nwos import http
from nwos.http import content_disposition, dispatch_rpc, request, Response
from nwos.service import db
from nwos.tools.misc import file_open, str2bool
from nwos.tools.translate import _

from nwos.addons.base.models.ir_qweb import render as qweb_render


_logger = logging.getLogger(__name__)


DBNAME_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9_.\-]+$'


def _get_database_localization_data():
    """Read country/currency metadata without requiring an active database."""
    with file_open('base/data/res_currency_data.xml', 'rb') as currency_file:
        currency_root = etree.parse(currency_file).getroot()
    currencies = []
    for record in currency_root.xpath('.//record[@model="res.currency"]'):
        values = {
            field.get('name'): field.text or ''
            for field in record.findall('field')
        }
        code = values.get('name')
        if code:
            currencies.append({
                'code': code,
                'name': values.get('full_name') or code,
                'symbol': values.get('symbol') or code,
            })

    with file_open('base/data/res_country_data.xml', 'rb') as country_file:
        country_root = etree.parse(country_file).getroot()
    country_currencies = {}
    for record in country_root.xpath('.//record[@model="res.country"]'):
        code_field = record.find('field[@name="code"]')
        currency_field = record.find('field[@name="currency_id"]')
        if code_field is not None and currency_field is not None:
            country_currencies[(code_field.text or '').lower()] = currency_field.get('ref')
    return sorted(currencies, key=lambda currency: currency['code']), country_currencies


ONBOARDING_MODULES = {
    'install_crm': 'crm',
    'install_sales': 'sale_management',
    'install_accounting': 'account',
    'install_inventory': 'stock',
    'install_purchase': 'purchase',
    'install_stock_requests': 'nwos_stock_request',
    'install_project': 'project',
    'install_website': 'website',
    'install_pos': 'point_of_sale',
    'install_manufacturing': 'mrp',
    'install_employees': 'hr',
}
ONBOARDING_OPTIONAL_MODULES = {
    'sop_purchase_agreements': ('install_purchase', 'purchase_requisition'),
    'sop_project_timesheets': ('install_project', 'hr_timesheet'),
    'sop_hr_attendance': ('install_employees', 'hr_attendance'),
    'sop_hr_skills': ('install_employees', 'hr_skills'),
}
ONBOARDING_SOP_SECTIONS = (
    {'option': 'install_crm', 'name': 'CRM', 'icon': 'fa-filter', 'sop': 'Capture inquiry → qualify → assign owner → follow up → close as won or lost.', 'questions': (
        {'name': 'sop_crm_lead_flow', 'label': 'How do inquiries enter the pipeline?', 'help': 'Qualify leads first when your team needs an intake stage before an opportunity.', 'type': 'select', 'default': 'opportunities', 'options': (('opportunities', 'Directly as opportunities'), ('leads', 'As leads to qualify first'))},
        {'name': 'sop_crm_auto_assignment', 'label': 'Automatically assign incoming leads', 'help': 'Enable rule-based assignment. Define team rules after sign-in.', 'type': 'boolean'},
        {'name': 'sop_crm_recurring_revenue', 'label': 'Track recurring revenue', 'help': 'Add recurring revenue forecasts to opportunities.', 'type': 'boolean'},
    )},
    {'option': 'install_sales', 'name': 'Sales', 'icon': 'fa-line-chart', 'sop': 'Prepare quote → review pricing → obtain acceptance → confirm → deliver and invoice.', 'questions': (
        {'name': 'sop_sales_discounts', 'label': 'Allow line-item discounts', 'help': 'Salespeople can enter a discount percentage on quotation lines.', 'type': 'boolean'},
        {'name': 'sop_sales_pricelists', 'label': 'Use customer or volume pricelists', 'help': 'Support different pricing rules by customer, quantity, or period.', 'type': 'boolean'},
        {'name': 'sop_sales_acceptance', 'label': 'How do customers confirm quotations?', 'help': 'Payment providers can be connected securely after sign-in.', 'type': 'select', 'default': 'signature', 'options': (('manual', 'Manual confirmation'), ('signature', 'Online signature'), ('signature_payment', 'Online signature and payment'))},
        {'name': 'sop_sales_invoice_policy', 'label': 'What should normally be invoiced?', 'help': 'This becomes the default policy for new products.', 'type': 'select', 'default': 'order', 'options': (('order', 'Ordered quantities'), ('delivery', 'Delivered quantities'))},
        {'name': 'sop_sales_lock_confirmed', 'label': 'Lock confirmed sales orders', 'help': 'Reduce untracked changes after customer confirmation.', 'type': 'boolean'},
    )},
    {'option': 'install_accounting', 'name': 'Accounting', 'icon': 'fa-calculator', 'sop': 'Issue or receive document → review → post → reconcile payment → close period.', 'questions': (
        {'name': 'sop_account_fiscal_localization', 'label': 'Fiscal localization / tax template', 'help': 'The country-specific chart of accounts and default sales and purchase taxes are installed automatically.', 'type': 'country_template'},
        {'name': 'sop_account_price_tax', 'label': 'How are sales prices normally entered?', 'help': 'Your country still determines the fiscal localization and taxes.', 'type': 'select', 'default': 'tax_excluded', 'options': (('tax_excluded', 'Tax excluded'), ('tax_included', 'Tax included'))},
        {'name': 'sop_account_tax_rounding', 'label': 'How should taxes be rounded?', 'help': 'Per-tax rounding is the platform default; per-line rounding may be required locally.', 'type': 'select', 'default': 'round_globally', 'options': (('round_globally', 'Round per tax'), ('round_per_line', 'Round per invoice line'))},
        {'name': 'sop_account_multi_currency', 'label': 'Use foreign currencies', 'help': 'Allow transactions and reporting in currencies other than the company currency.', 'type': 'boolean'},
        {'name': 'sop_account_analytic', 'label': 'Use analytic accounting', 'help': 'Track revenue and costs by project, department, contract, or cost center.', 'type': 'boolean'},
        {'name': 'sop_account_cash_rounding', 'label': 'Use cash rounding', 'help': 'Enable rounding methods for cash payments.', 'type': 'boolean'},
        {'name': 'sop_account_sales_receipts', 'label': 'Issue sales receipts', 'help': 'Support receipts in addition to standard customer invoices.', 'type': 'boolean'},
    )},
    {'option': 'install_inventory', 'name': 'Inventory', 'icon': 'fa-cubes', 'sop': 'Receive → inspect → put away → count → pick, pack, and ship.', 'questions': (
        {'name': 'sop_inventory_locations', 'label': 'Track bins and storage locations', 'help': 'Know the internal location of stock within a warehouse.', 'type': 'boolean'},
        {'name': 'sop_inventory_multistep', 'label': 'Use custom multi-step routes', 'help': 'Enable configurable receive, pick, pack, and ship routes. Detailed warehouse steps can be set after sign-in.', 'type': 'boolean'},
        {'name': 'sop_inventory_lots', 'label': 'Track lots or serial numbers', 'help': 'Enable product traceability; choose lot versus serial per product.', 'type': 'boolean'},
        {'name': 'sop_inventory_packages', 'label': 'Track packages', 'help': 'Group products into physical packages during transfers.', 'type': 'boolean'},
    )},
    {'option': 'install_purchase', 'name': 'Purchase', 'icon': 'fa-shopping-cart', 'sop': 'Request or RFQ → approve → confirm PO → receive → match bill → pay.', 'questions': (
        {'name': 'sop_purchase_approval', 'label': 'Require manager approval above a threshold', 'help': 'Route higher-value purchase orders through a second approval.', 'type': 'boolean'},
        {'name': 'sop_purchase_approval_amount', 'label': 'Approval threshold', 'help': 'Enter the amount in the company currency.', 'type': 'number', 'default': 5000, 'min': 0, 'max': 1000000000000, 'currency': True, 'enabled_by': 'sop_purchase_approval'},
        {'name': 'sop_purchase_lock', 'label': 'Lock confirmed purchase orders', 'help': 'Prevent casual edits after a purchase order is confirmed.', 'type': 'boolean'},
        {'name': 'sop_purchase_reminders', 'label': 'Send vendor receipt reminders', 'help': 'Allow scheduled reminders before expected receipt dates.', 'type': 'boolean', 'default': True},
        {'name': 'sop_purchase_agreements', 'label': 'Use blanket orders and purchase agreements', 'help': 'Install support for recurring and competitive purchasing agreements.', 'type': 'boolean'},
    )},
    {'option': 'install_stock_requests', 'name': 'Stock Requests', 'icon': 'fa-clipboard', 'sop': 'Request items → approve → source by transfer, purchase, or manufacture → track receipt and payment.', 'questions': (
        {'name': 'sop_stock_request_approver', 'label': 'Who should approve stock requests?', 'help': 'Manager choices use the employee organization chart. Advanced multi-step rules can be added after sign-in.', 'type': 'select', 'default': 'group', 'options': (('group', 'Any Stock Request approver'), ('manager', 'Requester’s manager'), ('department_manager', 'Department manager'))},
        {'name': 'sop_stock_request_approval_amount', 'label': 'Self-approval limit', 'help': 'Requests below this amount are automatically approved. Enter 0 to always require approval.', 'type': 'number', 'default': '0', 'min': 0, 'max': 1000000000000, 'currency': True},
        {'name': 'sop_stock_request_default_purpose', 'label': 'Default request purpose', 'help': 'Requesters can still change the purpose on individual requests.', 'type': 'select', 'default': 'stock', 'options': (('stock', 'Replenish stock'), ('office', 'Office / consumable'), ('project', 'Project'), ('manufacture', 'Manufacturing'))},
        {'name': 'sop_stock_request_default_source', 'label': 'Default sourcing method', 'help': 'Replenish follows each product’s transfer, manufacture, or buy routes.', 'type': 'select', 'default': 'buy', 'options': (('buy', 'Always create a request for quotation'), ('replenish', 'Use the product’s replenishment routes'))},
    )},
    {'option': 'install_project', 'name': 'Project', 'icon': 'fa-tasks', 'sop': 'Intake → plan and assign → execute and log → review → close.', 'questions': (
        {'name': 'sop_project_stages', 'label': 'Use stages across projects', 'help': 'Track the lifecycle of whole projects in addition to task stages.', 'type': 'boolean'},
        {'name': 'sop_project_dependencies', 'label': 'Allow task dependencies', 'help': 'Let teams identify tasks that block other work.', 'type': 'boolean'},
        {'name': 'sop_project_recurring', 'label': 'Allow recurring tasks', 'help': 'Support repeating operational work and checklists.', 'type': 'boolean'},
        {'name': 'sop_project_timesheets', 'label': 'Track time on tasks', 'help': 'Install timesheets for effort and service-delivery tracking.', 'type': 'boolean'},
    )},
    {'option': 'install_website', 'name': 'Website', 'icon': 'fa-globe', 'sop': 'Request content → draft → review → publish → periodically review.', 'questions': (
        {'name': 'sop_website_signup', 'label': 'Who can create a website account?', 'help': 'Invitation-only is the safer default for B2B sites.', 'type': 'select', 'default': 'b2b', 'options': (('b2b', 'Invited customers only'), ('b2c', 'Anyone can sign up'))},
        {'name': 'sop_website_cookie_bar', 'label': 'Show a cookie consent banner', 'help': 'Ask visitors for consent before optional cookies are used.', 'type': 'boolean', 'default': True},
        {'name': 'sop_website_block_third_party', 'label': 'Block third-party services before consent', 'help': 'Applies when the cookie consent banner is enabled.', 'type': 'boolean', 'default': True, 'enabled_by': 'sop_website_cookie_bar'},
    )},
    {'option': 'install_pos', 'name': 'Point of Sale', 'icon': 'fa-credit-card', 'sop': 'Open and count → sell or return → take payment → close → resolve variances.', 'questions': (
        {'name': 'sop_pos_manual_discounts', 'label': 'Allow cashier line discounts', 'help': 'Cashiers can enter a discount directly on an order line.', 'type': 'boolean', 'default': True},
        {'name': 'sop_pos_restrict_price', 'label': 'Restrict price changes to managers', 'help': 'Limit sensitive price controls for regular cashiers.', 'type': 'boolean', 'default': True},
        {'name': 'sop_pos_stock_timing', 'label': 'When should sales update inventory?', 'help': 'Real-time updates improve visibility; closing creates one transfer per session.', 'type': 'select', 'default': 'real', 'options': (('real', 'For every sale in real time'), ('closing', 'When the POS session closes'))},
        {'name': 'sop_pos_cash_limit', 'label': 'Enforce a maximum closing cash difference', 'help': 'Require a manager to resolve larger cash variances.', 'type': 'boolean'},
        {'name': 'sop_pos_cash_difference', 'label': 'Maximum cash difference', 'help': 'Enter the permitted difference in company currency.', 'type': 'number', 'default': 0, 'min': 0, 'max': 1000000000, 'currency': True, 'enabled_by': 'sop_pos_cash_limit'},
    )},
    {'option': 'install_manufacturing', 'name': 'Manufacturing', 'icon': 'fa-cogs', 'sop': 'Plan and approve BoM → reserve materials → perform operations → finish → review variance.', 'questions': (
        {'name': 'sop_mrp_workorders', 'label': 'Use work orders and work centers', 'help': 'Plan manufacturing as sequenced shop-floor operations.', 'type': 'boolean'},
        {'name': 'sop_mrp_dependencies', 'label': 'Enforce work-order dependencies', 'help': 'Prevent an operation from starting until prerequisite work is complete.', 'type': 'boolean', 'enabled_by': 'sop_mrp_workorders'},
        {'name': 'sop_mrp_byproducts', 'label': 'Record manufacturing by-products', 'help': 'Track secondary products generated by a production order.', 'type': 'boolean'},
        {'name': 'sop_mrp_unlock_orders', 'label': 'Let operators edit confirmed manufacturing orders', 'help': 'Use only when your SOP permits changes without a separate approval.', 'type': 'boolean'},
    )},
    {'option': 'install_employees', 'name': 'Employees', 'icon': 'fa-users', 'sop': 'Approve hire → create profile and access → onboard → maintain records → offboard.', 'questions': (
        {'name': 'sop_hr_attendance', 'label': 'Track employee attendance', 'help': 'Install check-in, check-out, and attendance reporting.', 'type': 'boolean'},
        {'name': 'sop_hr_skills', 'label': 'Track skills and resumes', 'help': 'Maintain employee capabilities, certifications, and experience.', 'type': 'boolean'},
        {'name': 'sop_hr_expiry_notice_days', 'label': 'Document expiry warning', 'help': 'Days before contract and work-permit expiry to alert HR.', 'type': 'number', 'default': 7, 'min': 0, 'max': 3650},
    )},
)
ONBOARDING_SOP_FIELDS = tuple(
    question['name']
    for section in ONBOARDING_SOP_SECTIONS
    for question in section['questions']
)
ONBOARDING_SOP_QUESTIONS = {
    question['name']: (section['option'], question)
    for section in ONBOARDING_SOP_SECTIONS
    for question in section['questions']
}
DATABASE_CREATION_PROGRESS = {}


def _update_database_creation_progress(
    token, stage, percent, message, detail='', level='info',
):
    if not token:
        return
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = DATABASE_CREATION_PROGRESS.setdefault(token, {
        'started_at': timestamp,
        'logs': [],
    })
    event = {
        'id': len(payload['logs']) + 1,
        'timestamp': timestamp,
        'stage': stage,
        'level': level,
        'message': message,
        'detail': detail,
    }
    payload['logs'].append(event)
    payload['logs'] = payload['logs'][-60:]
    payload.update({
        'stage': stage,
        'percent': percent,
        'message': message,
        'detail': detail,
    })


class Database(http.Controller):

    @staticmethod
    def _post_is_true(post, field_name):
        return str(post.get(field_name, '')).lower() in ('1', 'true', 'on', 'yes')

    def _get_onboarding_modules(self, post):
        module_names = [
            module_name
            for option, module_name in ONBOARDING_MODULES.items()
            if self._post_is_true(post, option)
        ]
        module_names.extend(
            module_name
            for option, (parent_option, module_name) in ONBOARDING_OPTIONAL_MODULES.items()
            if self._post_is_true(post, parent_option) and self._post_is_true(post, option)
        )
        return list(dict.fromkeys(module_names))

    def _validate_onboarding_sop(self, post):
        currency_code = post.get('currency_code')
        if currency_code:
            currencies, _country_currencies = _get_database_localization_data()
            if currency_code not in {currency['code'] for currency in currencies}:
                raise ValueError("Invalid company currency")
        if not self._post_is_true(post, 'sop_profile_submitted'):
            return
        selections = {
            'sop_crm_lead_flow': {'opportunities', 'leads'},
            'sop_sales_acceptance': {'manual', 'signature', 'signature_payment'},
            'sop_sales_invoice_policy': {'order', 'delivery'},
            'sop_account_price_tax': {'tax_excluded', 'tax_included'},
            'sop_account_tax_rounding': {'round_globally', 'round_per_line'},
            'sop_stock_request_approver': {'group', 'manager', 'department_manager'},
            'sop_stock_request_default_purpose': {'stock', 'office', 'project', 'manufacture'},
            'sop_stock_request_default_source': {'buy', 'replenish'},
            'sop_website_signup': {'b2b', 'b2c'},
            'sop_pos_stock_timing': {'real', 'closing'},
        }
        for field_name, allowed_values in selections.items():
            parent_option, question = ONBOARDING_SOP_QUESTIONS[field_name]
            if not self._post_is_true(post, parent_option):
                continue
            enabled_by = question.get('enabled_by')
            if enabled_by and not self._post_is_true(post, enabled_by):
                continue
            if post.get(field_name) and post[field_name] not in allowed_values:
                raise ValueError(f"Invalid onboarding value for {field_name}")
        numeric_fields = {
            'sop_purchase_approval_amount': (0, 1_000_000_000_000),
            'sop_stock_request_approval_amount': (0, 1_000_000_000_000),
            'sop_pos_cash_difference': (0, 1_000_000_000),
            'sop_hr_expiry_notice_days': (0, 3650),
        }
        for field_name, (minimum, maximum) in numeric_fields.items():
            parent_option, question = ONBOARDING_SOP_QUESTIONS[field_name]
            if not self._post_is_true(post, parent_option):
                continue
            enabled_by = question.get('enabled_by')
            if enabled_by and not self._post_is_true(post, enabled_by):
                continue
            if not post.get(field_name):
                continue
            try:
                value = float(post[field_name])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid onboarding number for {field_name}") from exc
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"Invalid onboarding number for {field_name}")
            if field_name == 'sop_hr_expiry_notice_days' and not value.is_integer():
                raise ValueError(f"Invalid onboarding number for {field_name}")

    @staticmethod
    def _set_implied_group(env, implied_group_xmlid, enabled):
        """Expose a project feature which has no res.config.settings field."""
        employee_group = env.ref('base.group_user').sudo()
        implied_group = env.ref(implied_group_xmlid).sudo()
        if enabled:
            employee_group._apply_group(implied_group)
        else:
            employee_group._remove_group(implied_group)

    def _apply_onboarding_sop(self, env, post):
        """Apply the submitted operating profile after its applications exist."""
        is_true = lambda name: self._post_is_true(post, name)
        if not is_true('sop_profile_submitted'):
            return
        settings_values = {}
        company_values = {}

        if is_true('install_crm'):
            auto_assignment = is_true('sop_crm_auto_assignment')
            settings_values.update({
                'group_use_lead': post.get('sop_crm_lead_flow') == 'leads',
                'group_use_recurring_revenues': is_true('sop_crm_recurring_revenue'),
                'crm_use_auto_assignment': auto_assignment,
                'crm_auto_assignment_action': 'auto' if auto_assignment else 'manual',
                'crm_auto_assignment_interval_type': 'days',
                'crm_auto_assignment_interval_number': 1,
            })

        if is_true('install_sales'):
            discounts = is_true('sop_sales_discounts')
            acceptance = post.get('sop_sales_acceptance', 'manual')
            settings_values.update({
                'group_discount_per_so_line': discounts,
                # The settings-view onchange is not invoked during database setup.
                'group_product_pricelist': discounts or is_true('sop_sales_pricelists'),
                'group_auto_done_setting': is_true('sop_sales_lock_confirmed'),
                'default_invoice_policy': (
                    'delivery' if post.get('sop_sales_invoice_policy') == 'delivery' else 'order'
                ),
            })
            company_values.update({
                'portal_confirmation_sign': acceptance in ('signature', 'signature_payment'),
                'portal_confirmation_pay': acceptance == 'signature_payment',
            })

        if is_true('install_accounting'):
            settings_values.update({
                'group_cash_rounding': is_true('sop_account_cash_rounding'),
                'group_multi_currency': is_true('sop_account_multi_currency'),
                'group_analytic_accounting': is_true('sop_account_analytic'),
                'show_sale_receipts': is_true('sop_account_sales_receipts'),
                'tax_calculation_rounding_method': (
                    'round_per_line'
                    if post.get('sop_account_tax_rounding') == 'round_per_line'
                    else 'round_globally'
                ),
            })
            settings_values['chart_template'] = (
                env.company.chart_template
                or env['account.chart.template']._guess_chart_template(env.company.country_id)
            )
            company_values['account_price_include'] = (
                'tax_included' if post.get('sop_account_price_tax') == 'tax_included'
                else 'tax_excluded'
            )

        if is_true('install_inventory'):
            multi_step = is_true('sop_inventory_multistep')
            settings_values.update({
                'group_stock_multi_locations': multi_step or is_true('sop_inventory_locations'),
                'group_stock_adv_location': multi_step,
                'group_stock_production_lot': is_true('sop_inventory_lots'),
                'group_stock_tracking_lot': is_true('sop_inventory_packages'),
            })

        if is_true('install_purchase'):
            approval = is_true('sop_purchase_approval')
            try:
                approval_amount = max(0.0, float(post.get('sop_purchase_approval_amount') or 0))
            except (TypeError, ValueError):
                approval_amount = 0.0
            settings_values.update({
                'lock_confirmed_po': is_true('sop_purchase_lock'),
                'po_order_approval': approval,
                'group_send_reminder': is_true('sop_purchase_reminders'),
            })
            if approval:
                settings_values['po_double_validation_amount'] = approval_amount

        if is_true('install_stock_requests'):
            try:
                self_approval_amount = max(
                    0.0,
                    float(post.get('sop_stock_request_approval_amount') or 0),
                )
            except (TypeError, ValueError):
                self_approval_amount = 0.0
            settings_values['stock_request_approval_amount'] = self_approval_amount
            env['ir.default'].set(
                'stock.request', 'purpose',
                post.get('sop_stock_request_default_purpose', 'stock'),
                company_id=env.company.id,
            )
            env['ir.default'].set(
                'stock.request.line', 'source_action',
                post.get('sop_stock_request_default_source', 'buy'),
                company_id=env.company.id,
            )
            approver_type = post.get('sop_stock_request_approver', 'group')
            if approver_type != 'group':
                env['stock.request.approval.rule'].create({
                    'name': 'Default stock request approval',
                    # First-match-wins: leave room for more specific rules.
                    'sequence': 9999,
                    'company_id': env.company.id,
                    'step_ids': [(0, 0, {
                        'name': 'Stock request approval',
                        'approver_type': approver_type,
                        'approval_mode': 'any',
                    })],
                })

        if is_true('install_project'):
            settings_values['group_project_stages'] = is_true('sop_project_stages')
            self._set_implied_group(
                env, 'project.group_project_task_dependencies',
                is_true('sop_project_dependencies'),
            )
            self._set_implied_group(
                env, 'project.group_project_recurring_tasks',
                is_true('sop_project_recurring'),
            )

        if is_true('install_website'):
            website = env['website'].search([('company_id', '=', env.company.id)], limit=1)
            if website:
                website.write({
                    'auth_signup_uninvited': (
                        'b2c' if post.get('sop_website_signup') == 'b2c' else 'b2b'
                    ),
                    'cookies_bar': is_true('sop_website_cookie_bar'),
                    'block_third_party_domains': (
                        is_true('sop_website_cookie_bar')
                        and is_true('sop_website_block_third_party')
                    ),
                })

        if is_true('install_pos'):
            try:
                cash_difference = max(0.0, float(post.get('sop_pos_cash_difference') or 0))
            except (TypeError, ValueError):
                cash_difference = 0.0
            pos_values = {
                'manual_discount': is_true('sop_pos_manual_discounts'),
                'restrict_price_control': is_true('sop_pos_restrict_price'),
                'set_maximum_difference': is_true('sop_pos_cash_limit'),
            }
            if is_true('sop_pos_cash_limit'):
                pos_values['amount_authorized_diff'] = cash_difference
            env['pos.config'].search([('company_id', '=', env.company.id)]).write(pos_values)
            company_values['point_of_sale_update_stock_quantities'] = (
                'closing' if post.get('sop_pos_stock_timing') == 'closing' else 'real'
            )

        if is_true('install_manufacturing'):
            workorders = is_true('sop_mrp_workorders')
            dependencies = workorders and is_true('sop_mrp_dependencies')
            settings_values.update({
                'group_mrp_routings': workorders,
                'group_mrp_byproducts': is_true('sop_mrp_byproducts'),
                'group_mrp_workorder_dependencies': dependencies,
                'group_unlocked_by_default': is_true('sop_mrp_unlock_orders'),
            })

        if is_true('install_employees'):
            try:
                notice_days = min(3650, max(0, int(post.get('sop_hr_expiry_notice_days') or 0)))
            except (TypeError, ValueError):
                notice_days = 0
            company_values.update({
                'contract_expiration_notice_period': notice_days,
                'work_permit_expiration_notice_period': notice_days,
            })

        if company_values:
            env.company.write(company_values)
        if settings_values:
            env['res.config.settings'].create(settings_values).execute()
        currency_code = post.get('currency_code')
        if currency_code:
            selected_currency = env['res.currency'].search([('name', '=', currency_code)], limit=1)
            if selected_currency and env.company.currency_id != selected_currency:
                env.company.currency_id = selected_currency

        # Keep the selected operating profile available for later setup guidance.
        app_prefixes = {
            'sop_crm_': 'install_crm',
            'sop_sales_': 'install_sales',
            'sop_account_': 'install_accounting',
            'sop_inventory_': 'install_inventory',
            'sop_purchase_': 'install_purchase',
            'sop_stock_request_': 'install_stock_requests',
            'sop_project_': 'install_project',
            'sop_website_': 'install_website',
            'sop_pos_': 'install_pos',
            'sop_mrp_': 'install_manufacturing',
            'sop_hr_': 'install_employees',
        }
        profile = {}
        for field in ONBOARDING_SOP_FIELDS:
            parent_option = next(
                (option for prefix, option in app_prefixes.items() if field.startswith(prefix)),
                None,
            )
            if not parent_option or not is_true(parent_option):
                continue
            question = ONBOARDING_SOP_QUESTIONS[field][1]
            enabled_by = question.get('enabled_by')
            if enabled_by and not is_true(enabled_by):
                continue
            if question['type'] == 'boolean':
                profile[field] = is_true(field)
            elif post.get(field) not in (None, ''):
                profile[field] = post[field]
        env['ir.config_parameter'].sudo().set_param(
            'web.onboarding.sop_profile', json.dumps({
                'version': 1,
                'answers': profile,
            }, sort_keys=True),
        )

    @http.route('/web/database/create/progress/<string:token>', type='http', auth="none")
    def create_progress(self, token):
        payload = DATABASE_CREATION_PROGRESS.get(token, {
            'stage': 'waiting',
            'percent': 2,
            'message': 'Waiting for setup to begin...',
            'detail': 'The creation request is being handed to the server.',
            'logs': [],
        })
        return request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json'), ('Cache-Control', 'no-store')],
        )

    def _render_template(self, **d):
        d.setdefault('manage', True)
        d.setdefault('create_values', {})
        d['insecure'] = nwos.tools.config.verify_admin_password('admin')
        d['list_db'] = nwos.tools.config['list_db']
        d['langs'] = nwos.service.db.exp_list_lang()
        d['countries'] = nwos.service.db.exp_list_countries()
        d['currencies'], d['country_currencies'] = _get_database_localization_data()
        d['pattern'] = DBNAME_PATTERN
        d['sop_sections'] = ONBOARDING_SOP_SECTIONS
        # databases list
        try:
            d['databases'] = http.db_list()
            d['incompatible_databases'] = nwos.service.db.list_db_incompatible(d['databases'])
        except nwos.exceptions.AccessDenied:
            d['databases'] = [request.db] if request.db else []

        templates = {}

        with file_open("web/static/src/public/database_manager.qweb.html", "r") as fd:
            templates['database_manager'] = fd.read()
        with file_open("web/static/src/public/database_manager.master_input.qweb.html", "r") as fd:
            templates['master_input'] = fd.read()
        with file_open("web/static/src/public/database_manager.create_form.qweb.html", "r") as fd:
            templates['create_form'] = fd.read()

        def load(template_name):
            fromstring = html.document_fromstring if template_name == 'database_manager' else html.fragment_fromstring
            return (fromstring(templates[template_name]), template_name)

        return qweb_render('database_manager', d, load)

    @http.route('/web/database/selector', type='http', auth="none")
    def selector(self, **kw):
        if request.db:
            request.env.cr.close()
        return self._render_template(manage=False)

    @http.route('/web/database/manager', type='http', auth="none")
    def manager(self, **kw):
        if request.db:
            request.env.cr.close()
        return self._render_template()

    @http.route('/web/database/create', type='http', auth="none", methods=['POST'], csrf=False)
    def create(self, master_pwd, name, lang, password, **post):
        progress_token = post.get('setup_token')
        def set_progress(stage, percent, message, detail='', level='info'):
            _update_database_creation_progress(
                progress_token, stage, percent, message, detail, level,
            )

        selected_app_names = [
            section['name']
            for section in ONBOARDING_SOP_SECTIONS
            if self._post_is_true(post, section['option'])
        ]
        set_progress(
            'validating', 3,
            'Setup request received',
            'Checking administrator, workspace, and localization inputs.',
        )
        insecure = nwos.tools.config.verify_admin_password('admin')
        if insecure and master_pwd:
            set_progress(
                'validating', 6,
                'Securing database management',
                'Replacing the initial database-manager password.',
            )
            dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
        try:
            if not re.match(DBNAME_PATTERN, name):
                raise Exception(_('Houston, we have a database naming issue! Make sure you only use letters, numbers, underscores, hyphens, or dots in the database name, and you\'ll be golden.'))
            self._validate_onboarding_sop(post)
            # country code could be = "False" which is actually True in python
            country_code = post.get('country_code') or False
            set_progress(
                'validating', 10,
                'Configuration validated',
                f"{len(selected_app_names)} application(s) selected; locale {lang}, currency {post.get('currency_code') or 'automatic'}.",
                'success',
            )
            set_progress(
                'database', 16,
                'Creating the database and core records',
                f"Initializing {name} with the core schema, administrator, language, and security records.",
            )
            dispatch_rpc('db', 'create_database', [master_pwd, name, self._post_is_true(post, 'demo'), lang, password, post['login'], country_code, post['phone']])
            set_progress(
                'database', 34,
                'Core database created',
                'The base schema and administrator account are ready.',
                'success',
            )
            credential = {'login': post['login'], 'password': password, 'type': 'password'}
            with nwos.modules.registry.Registry(name).cursor() as cr:
                env = nwos.api.Environment(cr, nwos.SUPERUSER_ID, {})
                set_progress(
                    'carbon', 39,
                    'Loading the new workspace registry',
                    'Starting the application environment and resolving auto-installed components.',
                )
                set_progress(
                    'carbon', 44,
                    'Initializing the Carbon interface',
                    'Preparing the NWOS shell, theme assets, and first-login experience.',
                )
                company_values = {
                    field: post[field].strip()
                    for field in ('street', 'city', 'zip', 'vat')
                    if post.get(field)
                }
                if post.get('company_name'):
                    company_values['name'] = post['company_name'].strip()
                if post.get('currency_code'):
                    currency = env['res.currency'].search([
                        ('name', '=', post['currency_code']),
                    ], limit=1)
                    if currency:
                        company_values['currency_id'] = currency.id
                for upload_name, company_field in (
                    ('company_logo', 'logo'),
                    ('company_logo_white', 'logo_white'),
                ):
                    upload = post.get(upload_name)
                    if upload and hasattr(upload, 'read'):
                        image_data = upload.read(5 * 1024 * 1024 + 1)
                        if len(image_data) > 5 * 1024 * 1024:
                            raise ValueError(f"{upload_name} must be smaller than 5 MB")
                        if image_data:
                            company_values[company_field] = base64.b64encode(image_data)
                            set_progress(
                                'company', 49,
                                f"Processing {company_field.replace('_', ' ')}",
                                'Validated and prepared the uploaded company image.',
                            )
                set_progress(
                    'company', 52,
                    'Applying company identity and localization',
                    f"Saving company details for {country_code.upper() if country_code else 'the selected country'} in {post.get('currency_code') or 'its default currency'}.",
                )
                if company_values:
                    env['res.company'].browse(1).write(company_values)
                set_progress(
                    'company', 58,
                    'Company profile configured',
                    'Identity, address, language, currency, and regional defaults have been applied.',
                    'success',
                )
                module_names = self._get_onboarding_modules(post)
                if module_names:
                    set_progress(
                        'applications', 63,
                        'Resolving application dependencies',
                        ', '.join(selected_app_names),
                    )
                    modules = env['ir.module.module'].search([
                        ('name', 'in', module_names),
                        ('state', '=', 'uninstalled'),
                    ])
                    set_progress(
                        'applications', 69,
                        'Installing selected applications',
                        f"Installing {len(modules)} selected package(s) and their required dependencies. This is often the longest step.",
                    )
                    modules.button_immediate_install()
                    set_progress(
                        'applications', 84,
                        'Application packages installed',
                        'Menus, security rules, models, and supporting data are ready.',
                        'success',
                    )
                else:
                    set_progress(
                        'applications', 84,
                        'Core workspace selected',
                        'No additional application packages need to be installed.',
                        'success',
                    )
            with nwos.modules.registry.Registry(name).cursor() as cr:
                env = nwos.api.Environment(cr, nwos.SUPERUSER_ID, {})
                set_progress(
                    'applications', 88,
                    'Applying your operating profile',
                    'Configuring approvals, workflows, access groups, tax behavior, and SOP preferences.',
                )
                self._apply_onboarding_sop(env, post)
                set_progress(
                    'applications', 92,
                    'Operating settings applied',
                    'Your selected application settings and SOP profile have been saved.',
                    'success',
                )
                set_progress(
                    'signin', 95,
                    'Preparing the administrator session',
                    'Authenticating the administrator and initializing the first workspace session.',
                )
                request.session.db = name
                request.env = env
                request.session.authenticate(env, credential)
                request._save_session(env)
                set_progress(
                    'signin', 98,
                    'Finalizing first sign-in',
                    'Saving the secure session and preparing the NWOS home screen.',
                )
            set_progress(
                'complete', 100,
                'Workspace ready',
                'Setup completed successfully. Opening NWOS now.',
                'success',
            )
            return request.redirect('/nwos')
        except Exception as e:
            _logger.exception("Database creation error.")
            if isinstance(e, nwos.exceptions.AccessDenied):
                error = "The master password is incorrect. Please try again."
            elif isinstance(e, db.DatabaseExists):
                error = "A database with this ID already exists. Open it below or retry with another ID."
            elif isinstance(e, ValueError):
                error = "One of the operating setup answers is invalid. Review your configuration and try again."
            else:
                error = "The database was created, but one or more applications or operating settings could not be applied. You can open the database or retry the setup."
            set_progress(
                'error', 100,
                'Workspace setup stopped',
                error,
                'error',
            )
        preserved_fields = (
            'login', 'company_name', 'street', 'city', 'zip', 'vat', 'lang',
            'country_code', 'currency_code', 'phone', 'demo', 'sop_profile_submitted',
            *ONBOARDING_MODULES, *ONBOARDING_SOP_FIELDS,
        )
        create_values = {field: post.get(field) for field in preserved_fields if post.get(field)}
        create_values['name'] = name
        return self._render_template(
            error=error,
            failed_database=name if name in http.db_list() else False,
            create_values=create_values,
        )

    @http.route('/web/database/duplicate', type='http', auth="none", methods=['POST'], csrf=False)
    def duplicate(self, master_pwd, name, new_name, neutralize_database=False):
        insecure = nwos.tools.config.verify_admin_password('admin')
        if insecure and master_pwd:
            dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
        try:
            if not re.match(DBNAME_PATTERN, new_name):
                raise Exception(_('Houston, we have a database naming issue! Make sure you only use letters, numbers, underscores, hyphens, or dots in the database name, and you\'ll be golden.'))
            dispatch_rpc('db', 'duplicate_database', [master_pwd, name, new_name, neutralize_database])
            if request.db == name:
                request.env.cr.close()  # duplicating a database leads to an unusable cursor
            return request.redirect('/web/database/manager')
        except Exception as e:
            _logger.exception("Database duplication error.")
            error = "Database duplication error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)

    @http.route('/web/database/drop', type='http', auth="none", methods=['POST'], csrf=False)
    def drop(self, master_pwd, name):
        insecure = nwos.tools.config.verify_admin_password('admin')
        if insecure and master_pwd:
            dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
        try:
            deleting_active_database = request.session.db == name
            if deleting_active_database:
                # Logout hooks still need a live registry. Clear the session and
                # close its cursor before PostgreSQL removes the database.
                request.session.logout()
                if request.env and request.env.cr:
                    request.env.cr.close()
            dispatch_rpc('db', 'drop', [master_pwd, name])
            return request.redirect('/web/database/manager')
        except Exception as e:
            _logger.exception("Database deletion error.")
            error = "Database deletion error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)

    @http.route('/web/database/backup', type='http', auth="none", methods=['POST'], csrf=False)
    def backup(self, master_pwd, name, backup_format='zip', filestore=True):
        filestore = str2bool(filestore)
        insecure = nwos.tools.config.verify_admin_password('admin')
        if insecure and master_pwd:
            dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
        try:
            nwos.service.db.check_super(master_pwd)
            if name not in http.db_list():
                raise Exception("Database %r is not known" % name)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            filename = "%s_%s.%s" % (name, ts, backup_format)
            headers = [
                ('Content-Type', 'application/octet-stream; charset=binary'),
                ('Content-Disposition', content_disposition(filename)),
            ]
            dump_stream = nwos.service.db.dump_db(name, None, backup_format, filestore)
            response = Response(dump_stream, headers=headers, direct_passthrough=True)
            return response
        except Exception as e:
            _logger.exception('Database.backup')
            error = "Database backup error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)

    @http.route('/web/database/restore', type='http', auth="none", methods=['POST'], csrf=False, max_content_length=None)
    def restore(self, master_pwd, backup_file, name, copy=False, neutralize_database=False):
        insecure = nwos.tools.config.verify_admin_password('admin')
        if insecure and master_pwd:
            dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
        try:
            data_file = None
            db.check_super(master_pwd)
            with tempfile.NamedTemporaryFile(delete=False) as data_file:
                backup_file.save(data_file)
            db.restore_db(name, data_file.name, str2bool(copy), neutralize_database)
            return request.redirect('/web/database/manager')
        except Exception as e:
            error = "Database restore error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)
        finally:
            if data_file:
                os.unlink(data_file.name)

    @http.route('/web/database/change_password', type='http', auth="none", methods=['POST'], csrf=False)
    def change_password(self, master_pwd, master_pwd_new):
        try:
            dispatch_rpc('db', 'change_admin_password', [master_pwd, master_pwd_new])
            return request.redirect('/web/database/manager')
        except Exception as e:
            error = "Master password update error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)

    @http.route('/web/database/list', type='jsonrpc', auth='none')
    def list(self):
        """
        Used by Mobile application for listing database
        :return: List of databases
        :rtype: list
        """
        return http.db_list()
