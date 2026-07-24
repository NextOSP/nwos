import base64

from dateutil.relativedelta import relativedelta

from nwos import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    rfid_bod_recipient_emails = fields.Text(
        string='Nextwaves Kit Report Recipients',
        help='Comma-separated email addresses for the automatic monthly PDF report.')

    def get_rfid_bod_report_data(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        end = today.replace(day=1) - relativedelta(days=1)
        start = end.replace(day=1)
        data = self.env['bod.dashboard'].with_company(self)._rfid_data(start, end)
        return {'date_from': start, 'date_to': end, **data}

    @api.model
    def _cron_send_rfid_bod_report(self):
        report = self.env.ref('nwos_rfid_bod.action_report_rfid_bod_monthly')
        for company in self.search([('rfid_bod_recipient_emails', '!=', False)]):
            emails = ','.join(
                email.strip() for email in company.rfid_bod_recipient_emails.replace(';', ',').split(',')
                if email.strip()
            )
            if not emails:
                continue
            pdf, _report_type = self.env['ir.actions.report'].with_company(company)._render_qweb_pdf(
                report.report_name, company.ids)
            report_data = company.get_rfid_bod_report_data()
            filename = 'Nextwaves Kit Report %s.pdf' % report_data['date_to'].strftime('%Y-%m')
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(pdf),
                'mimetype': 'application/pdf',
                'res_model': 'res.company',
                'res_id': company.id,
            })
            self.env['mail.mail'].create({
                'subject': _('Nextwaves Kit Monthly Report - %s', report_data['date_to'].strftime('%B %Y')),
                'body_html': _(
                    '<p>Please find attached the Nextwaves Kit report for %(date_from)s to %(date_to)s.</p>',
                    date_from=report_data['date_from'], date_to=report_data['date_to']),
                'email_to': emails,
                'attachment_ids': [(6, 0, attachment.ids)],
                'auto_delete': True,
            }).send()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rfid_bod_recipient_emails = fields.Text(
        related='company_id.rfid_bod_recipient_emails', readonly=False)
