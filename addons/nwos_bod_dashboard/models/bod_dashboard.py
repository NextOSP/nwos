# Part of NextOSP. See LICENSE file for full copyright and licensing details.
import json
import logging
import re
from datetime import timedelta

import requests

from nwos import api, fields, models
from nwos.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Dashboard section key -> the app (module technical name) that must be installed
# for that section to appear. This is the "depends on active module" logic.
SECTION_MODULES = {
    'sales': 'sale',
    'invoicing': 'account',
    'pipeline': 'crm',
    'purchase': 'purchase',
    'inventory': 'stock',
    'pos': 'point_of_sale',
}

# Only read-only AI tools are exposed to the board assistant. Write tools
# (prepare_* in mail.bot) are deliberately excluded so it can never mutate data.
AI_READONLY_TOOLS = {'search_records', 'read_record', 'sales_report', 'check_stock'}

VALID_PERIODS = ('month', 'quarter', 'year', 'last90')

# IBM Carbon data-visualization categorical palette (segment colors).
CARBON_PALETTE = [
    '#8a3ffc', '#1192e8', '#007d79', '#9f1853', '#fa4d56',
    '#198038', '#002d9c', '#ee538b', '#b28600', '#009d9a',
    '#012749', '#8a3800', '#a56eff', '#4589ff', '#6fdc8c',
]


class BodDashboard(models.AbstractModel):
    _name = 'bod.dashboard'
    _description = 'Board of Directors Executive Dashboard'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _active_sections(self):
        """Return the set of section keys whose module is installed."""
        installed = set(self.env['ir.module.module'].sudo().search([
            ('name', 'in', list(set(SECTION_MODULES.values()))),
            ('state', '=', 'installed'),
        ]).mapped('name'))
        # Guard against a model that isn't loaded yet (partial installs).
        return {
            key for key, module in SECTION_MODULES.items()
            if module in installed
        }

    def _period_range(self, period):
        """Return (start, end) dates for the requested period, plus the
        matching previous period (prev_start, prev_end) for deltas."""
        if period not in VALID_PERIODS:
            period = 'last90'
        today = fields.Date.context_today(self)
        if period == 'month':
            start = today.replace(day=1)
        elif period == 'quarter':
            start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
        elif period == 'year':
            start = today.replace(month=1, day=1)
        else:  # last90
            start = today - timedelta(days=90)
        length = (today - start) + timedelta(days=1)
        prev_end = start - timedelta(days=1)
        prev_start = start - length
        return start, today, prev_start, prev_end

    @staticmethod
    def _dt_domain(field, start, end):
        """Datetime-field domain covering the inclusive [start, end] date range."""
        return [
            (field, '>=', fields.Datetime.to_string(fields.Datetime.to_datetime(start))),
            (field, '<', fields.Datetime.to_string(
                fields.Datetime.to_datetime(end + timedelta(days=1)))),
        ]

    @staticmethod
    def _date_domain(field, start, end):
        return [(field, '>=', str(start)), (field, '<=', str(end))]

    def _money(self, amount):
        currency = self.env.company.currency_id
        return {'value': amount or 0.0, 'formatted': currency.format(amount or 0.0)}

    @staticmethod
    def _delta(current, previous):
        """Percentage change current vs previous, or None if not comparable."""
        if not previous:
            return None
        return round((current - previous) / previous * 100.0, 1)

    # ------------------------------------------------------------------
    # Public entry point (called by the /nwos_bod/data controller)
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, period='last90'):
        active = self._active_sections()
        start, end, prev_start, prev_end = self._period_range(period)
        currency = self.env.company.currency_id
        data = {
            'period': period if period in VALID_PERIODS else 'last90',
            'date_from': str(start),
            'date_to': str(end),
            'company': self.env.company.display_name,
            'currency': {'symbol': currency.symbol, 'position': currency.position},
            'sections': sorted(active),
            'ai_available': not self.env['mail.bot']._ai_configuration_error(
                self.env['mail.bot']._ai_get_settings(profile='report')),
        }
        # Each section is isolated: a failure in one must not blank the board.
        builders = {
            'sales': self._sales_data,
            'invoicing': self._invoicing_data,
            'pipeline': self._pipeline_data,
            'purchase': self._purchase_data,
            'inventory': self._inventory_data,
            'pos': self._pos_data,
        }
        for key in active:
            try:
                data[key] = builders[key](start, end, prev_start, prev_end)
            except (UserError, AccessError) as error:
                data[key] = {'error': str(error)}
            except Exception as error:  # pragma: no cover - defensive
                _logger.warning("BOD dashboard section %s failed: %s", key, error)
                data[key] = {'error': self.env._("This section could not be loaded.")}

        # Sales-pipeline funnel (snapshot, à la "at a glance").
        if 'sales' in active or 'pipeline' in active:
            try:
                data['pipeline_funnel'] = self._sales_pipeline(active)
            except (UserError, AccessError):
                data['pipeline_funnel'] = []
        return data

    # ------------------------------------------------------------------
    # Sales pipeline funnel ("at a glance")
    # ------------------------------------------------------------------
    def _funnel_segments(self, model, domain, groupby):
        """Group `model` by `groupby` and return colored segments sorted by count."""
        Model = self.env[model].with_context(active_test=False)
        field = Model._fields.get(groupby.split(':')[0])
        selection = None
        if field is not None and field.type == 'selection':
            selection = dict(field._description_selection(self.env))
        segments = []
        for group, count in Model._read_group(domain, [groupby], ['__count']):
            if not count:
                continue
            if field is not None and field.relational:
                label = group.display_name if group else self.env._("Undefined")
                value = group.id if group else False
            elif selection is not None:
                label = selection.get(group, group or self.env._("Undefined"))
                value = group
            else:
                label = group or self.env._("Undefined")
                value = group
            segments.append({'label': label, 'count': count, 'value': value})
        segments.sort(key=lambda seg: seg['count'], reverse=True)
        for index, seg in enumerate(segments):
            seg['color'] = CARBON_PALETTE[index % len(CARBON_PALETTE)]
        return segments

    def _funnel_bar(self, key, model, domain, groupby, label):
        segments = self._funnel_segments(model, domain, groupby)
        return {
            'key': key,
            'label': label,
            'model': model,
            'groupby': groupby,
            'domain': domain,
            'total': sum(seg['count'] for seg in segments),
            'segments': segments,
        }

    def _sales_pipeline(self, active):
        bars = []
        if 'pipeline' in active:  # crm
            self.env['crm.lead'].check_access('read')
            bars.append(self._funnel_bar(
                'leads', 'crm.lead', [('type', '=', 'lead')], 'stage_id',
                self.env._("Leads")))
            bars.append(self._funnel_bar(
                'deals', 'crm.lead', [('type', '=', 'opportunity')], 'stage_id',
                self.env._("Deals")))
        if 'sales' in active:  # sale
            self.env['sale.order'].check_access('read')
            bars.append(self._funnel_bar(
                'quotations', 'sale.order', [('state', '!=', 'sale')], 'state',
                self.env._("Quotations")))
            bars.append(self._funnel_bar(
                'orders', 'sale.order', [('state', '=', 'sale')], 'invoice_status',
                self.env._("Sales Orders")))
        return bars

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    def _sales_data(self, start, end, prev_start, prev_end):
        SO = self.env['sale.order']
        SO.check_access('read')
        base = [('state', '=', 'sale')]
        domain = base + self._dt_domain('date_order', start, end)
        prev_domain = base + self._dt_domain('date_order', prev_start, prev_end)

        [(revenue, count)] = SO._read_group(domain, [], ['amount_total:sum', '__count'])
        [(prev_revenue,)] = SO._read_group(prev_domain, [], ['amount_total:sum'])
        revenue = revenue or 0.0
        avg_order = (revenue / count) if count else 0.0

        # Top 5 customers by revenue.
        top_customers = [
            {'id': partner.id, 'name': partner.display_name, **self._money(amount)}
            for partner, amount in SO._read_group(
                domain, ['partner_id'], ['amount_total:sum'],
                order='amount_total:sum desc', limit=5)
            if partner
        ]
        # Top 5 products by invoiced-line subtotal.
        SOL = self.env['sale.order.line']
        line_domain = [('order_id.state', '=', 'sale'), ('display_type', '=', False)]
        line_domain += self._dt_domain('order_id.date_order', start, end)
        top_products = [
            {'id': product.id, 'name': product.display_name, **self._money(amount)}
            for product, amount in SOL._read_group(
                line_domain, ['product_id'], ['price_subtotal:sum'],
                order='price_subtotal:sum desc', limit=5)
            if product
        ]
        # Revenue trend by month across the period.
        trend = [
            {'label': month.strftime('%Y-%m') if month else '', 'value': amount or 0.0}
            for month, amount in SO._read_group(
                domain, ['date_order:month'], ['amount_total:sum'],
                order='date_order:month asc')
        ]
        salespeople = []
        for user, amount, user_order_count in SO._read_group(
            domain, ['user_id'], ['amount_total:sum', '__count'],
            order='amount_total:sum desc', limit=10):
            amount = amount or 0.0
            salespeople.append({
                'id': user.id if user else False,
                'name': user.display_name if user else self.env._("Undefined"),
                'order_count': user_order_count,
                'avg_order': self._money(amount / user_order_count if user_order_count else 0.0),
                'share': round(amount / revenue * 100.0, 1) if revenue else 0.0,
                **self._money(amount),
            })
        return {
            'revenue': self._money(revenue),
            'revenue_delta': self._delta(revenue, prev_revenue or 0.0),
            'order_count': count,
            'avg_order': self._money(avg_order),
            'top_customers': top_customers,
            'top_products': top_products,
            'trend': trend,
            'salespeople': salespeople,
        }

    def _invoicing_data(self, start, end, prev_start, prev_end):
        AM = self.env['account.move']
        AM.check_access('read')
        today = fields.Date.context_today(self)
        posted_out = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]

        invoiced_domain = posted_out + self._date_domain('invoice_date', start, end)
        [(invoiced,)] = AM._read_group(invoiced_domain, [], ['amount_total_signed:sum'])

        overdue_domain = posted_out + [
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('invoice_date_due', '<', str(today)),
        ]
        [(overdue, overdue_count)] = AM._read_group(
            overdue_domain, [], ['amount_residual_signed:sum', '__count'])

        unpaid_domain = posted_out + [('payment_state', 'in', ('not_paid', 'partial'))]
        [(unpaid,)] = AM._read_group(unpaid_domain, [], ['amount_residual_signed:sum'])

        return {
            'invoiced': self._money(invoiced or 0.0),
            'overdue': self._money(overdue or 0.0),
            'overdue_count': overdue_count,
            'unpaid': self._money(unpaid or 0.0),
        }

    def _pipeline_data(self, start, end, prev_start, prev_end):
        Lead = self.env['crm.lead']
        Lead.check_access('read')
        domain = [('type', '=', 'opportunity'), ('active', '=', True),
                  ('probability', '<', 100), ('probability', '>', 0)]
        [(count, expected, weighted)] = Lead._read_group(
            domain, [], ['__count', 'expected_revenue:sum', 'prorated_revenue:sum'])
        closing_domain = domain + self._date_domain('date_deadline', start, end)
        [(closing_count, closing_value)] = Lead._read_group(
            closing_domain, [], ['__count', 'expected_revenue:sum'])
        return {
            'open_count': count,
            'expected': self._money(expected or 0.0),
            'weighted': self._money(weighted or 0.0),
            'closing_count': closing_count,
            'closing_value': self._money(closing_value or 0.0),
        }

    def _purchase_data(self, start, end, prev_start, prev_end):
        PO = self.env['purchase.order']
        PO.check_access('read')
        domain = [('state', 'in', ('purchase', 'done'))]
        domain += self._dt_domain('date_order', start, end)
        [(spend, count)] = PO._read_group(domain, [], ['amount_total:sum', '__count'])
        return {
            'committed': self._money(spend or 0.0),
            'order_count': count,
        }

    def _inventory_data(self, start, end, prev_start, prev_end):
        result = {}
        if 'stock.valuation.layer' in self.env:
            SVL = self.env['stock.valuation.layer']
            SVL.check_access('read')
            [(value,)] = SVL._read_group([], [], ['value:sum'])
            result['valuation'] = self._money(value or 0.0)
        # Storable products currently out of stock.
        Product = self.env['product.product']
        out_of_stock = Product.search_count([
            ('type', '=', 'consu'), ('is_storable', '=', True),
            ('qty_available', '<=', 0),
        ]) if 'is_storable' in Product._fields else 0
        result['out_of_stock'] = out_of_stock
        return result

    def _pos_data(self, start, end, prev_start, prev_end):
        POS = self.env['pos.order']
        POS.check_access('read')
        domain = [('state', 'in', ('paid', 'done'))]
        domain += self._dt_domain('date_order', start, end)
        [(total, count)] = POS._read_group(domain, [], ['amount_total:sum', '__count'])
        return {
            'total': self._money(total or 0.0),
            'order_count': count,
        }

    # ------------------------------------------------------------------
    # AI assistant (reuses the existing mail.bot LLM integration)
    # ------------------------------------------------------------------
    @staticmethod
    def _plain_text(content):
        """Strip Markdown so the answer renders cleanly as plain text.

        Kept self-contained so the assistant does not depend on a specific
        version of mail.bot's private helpers being loaded.
        """
        content = str(content or '').strip()
        content = re.sub(r'(?m)^\s{0,3}#{1,6}\s*', '', content)
        content = re.sub(r'\*\*([^*\n]+)\*\*', r'\1', content)
        content = re.sub(r'__([^_\n]+)__', r'\1', content)
        content = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'\1', content)
        content = content.replace('**', '').replace('__', '')
        content = re.sub(r'`([^`\n]+)`', r'\1', content)
        return content

    @api.model
    def ask_ai(self, question, dashboard_context=None):
        question = (question or '').strip()
        if not question:
            return {'error': self.env._("Please type a question.")}

        bot = self.env['mail.bot']
        settings = bot._ai_get_settings(profile='report')
        error = bot._ai_configuration_error(settings)
        if error:
            return {'error': error}

        tools = [
            tool for tool in bot._ai_tool_definitions()
            if (tool.get('function') or {}).get('name') in AI_READONLY_TOOLS
        ]
        system_prompt = (
            "You are the executive assistant for the Board of Directors inside "
            "the NWOS/Flectra ERP. Answer concisely and factually in the same "
            "language as the user's question. Use the provided read-only tools to "
            "fetch real ERP data (sales, invoices, stock) before answering; never "
            "invent numbers. Focus on what matters to executives: revenue, growth, "
            "receivables, pipeline. The chat renders plain text only, so do not use "
            "Markdown. If a module or figure is unavailable, say so briefly."
        )
        context_lines = [f"Current user: {self.env.user.display_name}"]
        if dashboard_context:
            try:
                context_lines.append(
                    "Currently displayed dashboard KPIs (JSON): "
                    + json.dumps(dashboard_context, ensure_ascii=False)[:4000])
            except (TypeError, ValueError):
                pass
        context_lines.append(f"Question: {question}")
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': "\n".join(context_lines)},
        ]

        try:
            assistant = bot._ai_chat_completion(settings, messages, tools=tools)
            for _round in range(2):  # bounded tool loop, mirrors mail.bot
                tool_calls = assistant.get('tool_calls') or []
                if not tool_calls:
                    break
                tool_messages = []
                for tool_call in tool_calls[:4]:
                    name, arguments = bot._ai_parse_tool_call(tool_call)
                    if name not in AI_READONLY_TOOLS:
                        continue
                    result = bot._ai_execute_tool(name, arguments)
                    tool_messages.append({
                        'role': 'tool',
                        'tool_call_id': tool_call.get('id') or name,
                        'content': bot._ai_json_dumps(result, limit=6000),
                    })
                if not tool_messages:
                    break
                messages.append(assistant)
                messages.extend(tool_messages)
                assistant = bot._ai_chat_completion(settings, messages, tools=tools)

            content = (assistant.get('content') or '').strip()
            if not content:
                return {'answer': self.env._("I could not produce an answer.")}
            return {'answer': self._plain_text(content)}
        except requests.RequestException as error:
            _logger.warning("BOD dashboard AI request failed: %s", error)
            return {'error': self.env._("The AI provider request failed: %s", error)}
        except (ValueError, KeyError, TypeError, UserError, AccessError) as error:
            _logger.warning("BOD dashboard AI processing failed: %s", error)
            return {'error': self.env._("I could not complete that AI request: %s", error)}
