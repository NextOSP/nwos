from nwos import api, fields, models, _
from nwos.exceptions import UserError
from nwos.addons.project.models.project_task import CLOSED_STATES


class ProjectProject(models.Model):
    _inherit = 'project.project'

    rfid_site_id = fields.Many2one(
        'rfid.service.site', string='Nextwaves Kit Site', index=True, copy=False)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    rfid_site_id = fields.Many2one(
        'rfid.service.site', string='Nextwaves Kit Site', index=True, copy=True)
    rfid_task_kind = fields.Selection([
        ('delivery', 'Delivery Coordination'),
        ('installation', 'Hardware Installation'),
        ('configuration', 'Configuration'),
        ('commissioning', 'Commissioning'),
        ('training', 'Training'),
        ('acceptance', 'Customer Acceptance'),
    ], string='Kit Task Type', copy=True)
    rfid_timesheet_required = fields.Boolean(
        string='Timesheet Required', copy=True)
    rfid_payment_blocked = fields.Boolean(
        related='rfid_site_id.payment_blocked', string='Payment Blocked')

    def write(self, vals):
        if 'state' in vals and vals['state'] in CLOSED_STATES:
            for task in self:
                if task.rfid_timesheet_required and not task.timesheet_ids.filtered(
                        lambda line: line.unit_amount > 0):
                    raise UserError(_(
                        "Log technician time before completing Kit task '%s'.",
                        task.display_name,
                    ))
        if vals.get('state') and vals['state'] not in ('04_waiting_normal', '1_canceled'):
            blocked = self.filtered(
                lambda task: task.rfid_site_id and task.rfid_site_id.payment_blocked)
            if blocked:
                raise UserError(_(
                    'Kit payment has not been released for: %s',
                    ', '.join(blocked.mapped('rfid_site_id.display_name')),
                ))
        result = super().write(vals)
        if vals.get('state') in CLOSED_STATES:
            for site in self.mapped('rfid_site_id').filtered(
                    lambda record: record.state in ('ready', 'in_delivery', 'in_installation')):
                implementation_tasks = site.installation_project_id.task_ids.filtered(
                    lambda task: task.rfid_task_kind != 'acceptance')
                if site.delivery_completed and implementation_tasks and all(
                        task.state in CLOSED_STATES for task in implementation_tasks):
                    site.state = 'awaiting_acceptance'
        return result
