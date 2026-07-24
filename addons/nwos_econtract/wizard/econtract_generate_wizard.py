# -*- coding: utf-8 -*-
from nwos import _, api, fields, models
from nwos.exceptions import UserError


class EContractGenerateWizard(models.TransientModel):
    _name = 'econtract.generate.wizard'
    _description = 'Generate eContract from a record'

    res_model = fields.Char('Source Model', required=True)
    res_id = fields.Integer('Source Id', required=True)
    source_display = fields.Char('Source Document', compute='_compute_source_display')
    template_id = fields.Many2one(
        'econtract.template', string='Template', required=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    open_after = fields.Boolean('Open contract after creation', default=True)

    @api.depends('res_model', 'res_id')
    def _compute_source_display(self):
        for wiz in self:
            display = False
            if wiz.res_model and wiz.res_id:
                rec = self.env[wiz.res_model].browse(wiz.res_id).exists()
                display = rec.display_name if rec else False
            wiz.source_display = display

    @api.model
    def action_open(self, record):
        """Return an action opening this wizard for *record*."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Contract'),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': record._name,
                'default_res_id': record.id,
            },
        }

    def action_generate(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            raise UserError(_("The source document no longer exists."))
        contract = self.env['econtract.contract'].create_from_record(self.template_id, record)
        if not self.open_after:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contract'),
            'res_model': 'econtract.contract',
            'res_id': contract.id,
            'view_mode': 'form',
            'target': 'current',
        }
