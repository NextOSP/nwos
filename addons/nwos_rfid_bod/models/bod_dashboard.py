from datetime import timedelta

from nwos import api, fields, models


class BodDashboard(models.AbstractModel):
    _inherit = 'bod.dashboard'

    @api.model
    def get_dashboard_data(self, period='last90'):
        data = super().get_dashboard_data(period=period)
        start = fields.Date.to_date(data['date_from'])
        end = fields.Date.to_date(data['date_to'])
        data['sections'] = sorted(set(data.get('sections', [])) | {'rfid'})
        data['company_id'] = self.env.company.id
        data['rfid'] = self._rfid_data(start, end)
        return data

    def _rfid_data(self, start, end):
        Site = self.env['rfid.service.site'].sudo()
        Subscription = self.env['rfid.subscription'].sudo()
        Ticket = self.env['helpdesk.ticket'].sudo()
        Task = self.env['project.task'].sudo()
        Timesheet = self.env['account.analytic.line'].sudo()
        SaleLine = self.env['sale.order.line'].sudo()

        sites = Site.search([('company_id', '=', self.env.company.id)])
        active_sites = sites.filtered(lambda site: site.state == 'active')
        accepted = sites.filtered(
            lambda site: site.accepted_on
            and start <= fields.Date.to_date(site.accepted_on) <= end)
        delivered = sites.filtered(
            lambda site: site.actual_delivery_date
            and start <= fields.Date.to_date(site.actual_delivery_date) <= end)
        on_time_delivery = delivered.filtered(
            lambda site: site.planned_delivery_date
            and site.actual_delivery_date <= site.planned_delivery_date)
        on_time_install = accepted.filtered(
            lambda site: site.planned_installation_date
            and site.accepted_on <= site.planned_installation_date)

        state_labels = dict(Site._fields['state']._description_selection(self.env))
        by_state = [
            {'key': state, 'label': state_labels.get(state, state), 'count': count}
            for state, count in Site._read_group(
                [('company_id', '=', self.env.company.id)], ['state'], ['__count'],
                order='__count desc')
        ]

        subscriptions = Subscription.search([
            ('company_id', '=', self.env.company.id), ('state', '=', 'active')])
        mrr = sum(subscriptions.mapped('mrr'))
        overdue_subscriptions = subscriptions.filtered(
            lambda subscription: subscription.collection_state == 'overdue')

        ticket_domain = [
            ('company_id', 'in', [self.env.company.id, False]),
            ('rfid_site_id', '!=', False),
            ('is_closed', '=', False),
        ]
        open_tickets = Ticket.search_count(ticket_domain)
        sla_failed = Ticket.search_count(ticket_domain + [('sla_fail', '=', True)])

        task_domain = [
            ('company_id', 'in', [self.env.company.id, False]),
            ('rfid_site_id', '!=', False),
            ('state', 'not in', ['1_done', '1_canceled']),
            ('date_deadline', '<', fields.Date.context_today(self)),
        ]
        overdue_tasks = Task.search_count(task_domain)
        hours = sum(Timesheet.search([
            ('company_id', '=', self.env.company.id),
            ('task_id.rfid_site_id', '!=', False),
            ('date', '>=', start), ('date', '<=', end),
        ]).mapped('unit_amount'))

        lead_times = [
            (site.accepted_on - site.sale_order_id.date_order).total_seconds() / 86400
            for site in accepted
            if site.sale_order_id.date_order
            and site.accepted_on >= site.sale_order_id.date_order
        ]
        read_rates = active_sites.filtered(lambda site: site.actual_read_rate > 0).mapped('actual_read_rate')

        kit_lines = SaleLine.search([
            ('company_id', '=', self.env.company.id),
            ('order_id.state', '=', 'sale'),
            ('rfid_line_role', '=', 'starter_kit'),
            ('order_id.date_order', '>=', fields.Datetime.to_datetime(start)),
            ('order_id.date_order', '<', fields.Datetime.to_datetime(end + timedelta(days=1))),
        ])
        kit_revenue = sum(kit_lines.mapped('price_subtotal'))
        estimated_cost = sum(
            line.product_id.standard_price * line.product_uom_qty for line in kit_lines)

        return {
            'site_count': len(sites),
            'active_sites': len(active_sites),
            'new_activations': len(accepted),
            'by_state': by_state,
            'kit_revenue': self._money(kit_revenue),
            'estimated_gross_margin': self._money(kit_revenue - estimated_cost),
            'mrr': self._money(mrr),
            'arr': self._money(mrr * 12),
            'active_subscriptions': len(subscriptions),
            'overdue_subscriptions': len(overdue_subscriptions),
            'open_tickets': open_tickets,
            'sla_failed_tickets': sla_failed,
            'overdue_tasks': overdue_tasks,
            'technician_hours': round(hours, 1),
            'on_time_delivery_pct': round(len(on_time_delivery) / len(delivered) * 100, 1) if delivered else None,
            'on_time_install_pct': round(len(on_time_install) / len(accepted) * 100, 1) if accepted else None,
            'average_lead_days': round(sum(lead_times) / len(lead_times), 1) if lead_times else None,
            'average_read_rate': round(sum(read_rates) / len(read_rates), 1) if read_rates else None,
        }
