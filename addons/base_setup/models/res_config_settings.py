# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import json
import requests

from nwos import api, fields, models, _
from nwos.exceptions import UserError
from nwos.tools.ai import AI_MODEL_PROFILES, AI_PROVIDER_DEFAULTS, AI_PROVIDER_SELECTION, get_ai_settings


AI_MODEL_CACHE_PARAM = 'base.ai.model_list'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    is_root_company = fields.Boolean(compute='_compute_is_root_company')
    module_base_import = fields.Boolean("Allow users to import data from CSV/XLS/XLSX/ODS files")
    module_google_calendar = fields.Boolean(
        string='Allow the users to synchronize their calendar  with Google Calendar')
    module_microsoft_calendar = fields.Boolean(
        string='Allow the users to synchronize their calendar with Outlook Calendar')
    module_mail_plugin = fields.Boolean(
        string='Allow integration with the mail plugins'
    )
    module_auth_oauth = fields.Boolean("Use external authentication providers (OAuth)")
    module_auth_ldap = fields.Boolean("LDAP Authentication")
    module_account_inter_company_rules = fields.Boolean("Manage Inter Company")
    module_voip = fields.Boolean("Phone")
    module_web_unsplash = fields.Boolean("Unsplash Image Library")
    module_sms = fields.Boolean("SMS")
    module_partner_autocomplete = fields.Boolean("Partner Autocomplete")
    module_base_geolocalize = fields.Boolean("GeoLocalize")
    module_google_recaptcha = fields.Boolean("reCAPTCHA")
    module_website_cf_turnstile = fields.Boolean("Cloudflare Turnstile")
    module_google_address_autocomplete = fields.Boolean("Google Address Autocomplete")
    report_footer = fields.Html(related="company_id.report_footer", string='Custom Report Footer', help="Footer text displayed at the bottom of all reports.", readonly=False)
    group_multi_currency = fields.Boolean(string='Multi-Currencies',
            implied_group='base.group_multi_currency',
            help="Allows to work in a multi currency environment")
    external_report_layout_id = fields.Many2one(related="company_id.external_report_layout_id")
    show_effect = fields.Boolean(string="Show Effect", config_parameter='base_setup.show_effect')
    company_count = fields.Integer('Number of Companies', compute="_compute_company_count")
    active_user_count = fields.Integer('Number of Active Users', compute="_compute_active_user_count")
    language_count = fields.Integer('Number of Languages', compute="_compute_language_count")
    company_name = fields.Char(related="company_id.display_name", string="Company Name")
    company_informations = fields.Text(compute="_compute_company_informations")
    company_country_code = fields.Char(related="company_id.country_id.code", string="Company Country Code", readonly=True)
    company_country_group_codes = fields.Json(related="company_id.country_id.country_group_codes")
    profiling_enabled_until = fields.Datetime("Profiling enabled until", config_parameter='base.profiling_enabled_until')
    ai_enabled = fields.Boolean(
        string='AI',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_provider = fields.Selection(
        AI_PROVIDER_SELECTION,
        string='AI Provider',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_endpoint = fields.Char(
        string='Base URL',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_model_id = fields.Selection(
        selection='_get_ai_model_selection',
        string='Model',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_model = fields.Char(
        string='Model ID',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_small_model_id = fields.Selection(
        selection='_get_ai_model_selection',
        string='Fast / Small Model',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_small_model = fields.Char(
        string='Fast / Small Model ID',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_intelligent_model_id = fields.Selection(
        selection='_get_ai_model_selection',
        string='Intelligent Model',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_intelligent_model = fields.Char(
        string='Intelligent Model ID',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_email_model_id = fields.Selection(
        selection='_get_ai_model_selection',
        string='Email Model',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_email_model = fields.Char(
        string='Email Model ID',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_report_model_id = fields.Selection(
        selection='_get_ai_model_selection',
        string='Report Model',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_report_model = fields.Char(
        string='Report Model ID',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)
    ai_api_key = fields.Char(
        string='API Key',
        compute='_compute_ai_settings',
        inverse='_inverse_ai_settings',
        readonly=False)

    @api.model
    def _get_ai_settings_values(self):
        ICP = self.env['ir.config_parameter'].sudo()
        default_settings = get_ai_settings(self.env, profile='default', legacy_prefix='crm.ai_lead_scoring')
        provider = default_settings['provider']
        values = {
            'ai_enabled': default_settings['enabled'],
            'ai_provider': provider,
            'ai_endpoint': default_settings['endpoint'],
            'ai_model': default_settings['model'],
            'ai_api_key': default_settings['api_key'],
        }

        for profile, meta in AI_MODEL_PROFILES.items():
            field_name = meta['field']
            selection_field = meta['selection_field']
            if profile != 'default':
                values[field_name] = (ICP.get_param(meta['param'], default=None) or '').strip()
            values[selection_field] = values[field_name] or False
        return values

    @api.model
    def get_values(self):
        res = super().get_values()
        res.update(self._get_ai_settings_values())
        return res

    def set_values(self):
        for setting in self:
            for meta in AI_MODEL_PROFILES.values():
                if setting[meta['selection_field']]:
                    setting[meta['field']] = setting[meta['selection_field']]
        result = super().set_values()
        self._set_ai_settings_values()
        return result

    def open_company(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Company',
            'view_mode': 'form',
            'res_model': 'res.company',
            'res_id': self.env.company.id,
            'target': 'current',
        }

    def open_new_user_default_groups(self):
        default_group = self.env.ref('base.default_user_group', raise_if_not_found=False)
        if not default_group:
            default_group = self.env['res.groups'].create({
                'name': _('Default access for new users'),
            })
            self.env['ir.model.data'].create({
                'name': 'default_user_group',
                'module': 'base',
                'res_id': default_group.id,
                'model': 'res.groups',
                'noupdate': True,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Edit new user default group"),
            'view_mode': 'form',
            'res_model': 'res.groups',
            'res_id': default_group.id,
            'views': [(self.env.ref('base.view_default_groups_form').id, 'form')],
            'target': 'new',
        }

    @api.model
    def _prepare_report_view_action(self, template):
        template_id = self.env.ref(template)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.ui.view',
            'view_mode': 'form',
            'res_id': template_id.id,
        }

    def edit_external_header(self):
        if not self.external_report_layout_id:
            return False
        return self._prepare_report_view_action(self.external_report_layout_id.key)

    @api.depends_context('uid')
    def _compute_ai_settings(self):
        values = self._get_ai_settings_values()
        for setting in self:
            for field_name, value in values.items():
                setting[field_name] = value

    def _inverse_ai_settings(self):
        self._set_ai_settings_values()

    def _set_ai_settings_values(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for setting in self:
            ai_model = setting.ai_model_id or setting.ai_model or ''
            ICP.set_param('base.ai.enabled', setting.ai_enabled)
            ICP.set_param('base.ai.provider', setting.ai_provider or 'openrouter')
            ICP.set_param('base.ai.endpoint', (setting.ai_endpoint or '').strip() or False)
            ICP.set_param('base.ai.model', ai_model.strip() or False)
            ICP.set_param('base.ai.api_key', (setting.ai_api_key or '').strip() or False)
            for profile, meta in AI_MODEL_PROFILES.items():
                if profile == 'default':
                    continue
                ICP.set_param('base.ai.model.%s' % profile, (setting[meta['field']] or '').strip() or False)

    @api.onchange('ai_provider')
    def _onchange_ai_provider(self):
        for setting in self:
            defaults = AI_PROVIDER_DEFAULTS.get(setting.ai_provider)
            if not defaults:
                continue
            if setting.ai_provider != 'custom':
                setting.ai_endpoint = defaults['endpoint']
                for meta in AI_MODEL_PROFILES.values():
                    model = defaults.get(meta['default_key']) or defaults['model']
                    setting[meta['field']] = model
                    setting[meta['selection_field']] = model if self._ai_model_is_in_selection(model) else False
            else:
                for meta in AI_MODEL_PROFILES.values():
                    setting[meta['selection_field']] = False

    @api.onchange(
        'ai_model_id',
        'ai_small_model_id',
        'ai_intelligent_model_id',
        'ai_email_model_id',
        'ai_report_model_id',
    )
    def _onchange_ai_model_id(self):
        for setting in self:
            for meta in AI_MODEL_PROFILES.values():
                if setting[meta['selection_field']]:
                    setting[meta['field']] = setting[meta['selection_field']]

    @api.onchange(
        'ai_model',
        'ai_small_model',
        'ai_intelligent_model',
        'ai_email_model',
        'ai_report_model',
    )
    def _onchange_ai_model(self):
        for setting in self:
            for meta in AI_MODEL_PROFILES.values():
                model = setting[meta['field']]
                setting[meta['selection_field']] = model if self._ai_model_is_in_selection(model) else False

    @api.model
    def _get_ai_model_cache(self):
        raw_cache = self.env['ir.config_parameter'].sudo().get_param(AI_MODEL_CACHE_PARAM) or '{}'
        try:
            cache = json.loads(raw_cache)
        except ValueError:
            return {}
        return cache if isinstance(cache, dict) else {}

    @api.model
    def _set_ai_model_cache(self, provider, endpoint, model_values):
        cache = self._get_ai_model_cache()
        cache[f'{provider}|{endpoint}'] = model_values
        self.env['ir.config_parameter'].sudo().set_param(
            AI_MODEL_CACHE_PARAM,
            json.dumps(cache, sort_keys=True),
        )

    @api.model
    def _iter_ai_model_cache_values(self):
        for model_values in self._get_ai_model_cache().values():
            if isinstance(model_values, list):
                yield from model_values

    @api.model
    def _get_ai_model_selection(self):
        selection = []
        seen_model_ids = set()
        for model_value in self._iter_ai_model_cache_values():
            if not isinstance(model_value, dict):
                continue
            model_id = str(model_value.get('model_id') or '').strip()
            if not model_id or model_id in seen_model_ids:
                continue
            seen_model_ids.add(model_id)
            name = str(model_value.get('name') or model_id).strip() or model_id
            selection.append((model_id, name if name == model_id else f'{name} ({model_id})'))

        values = self._get_ai_settings_values()
        for meta in AI_MODEL_PROFILES.values():
            configured_model = values.get(meta['field'])
            if configured_model and configured_model not in seen_model_ids:
                seen_model_ids.add(configured_model)
                selection.append((configured_model, configured_model))
        return selection

    @api.model
    def _ai_model_is_in_selection(self, model_id):
        return bool(model_id) and model_id in {value for value, _label in self._get_ai_model_selection()}

    @api.model
    def _ai_models_url(self, endpoint):
        endpoint = (endpoint or '').strip().rstrip('/')
        if endpoint.endswith('/chat/completions'):
            endpoint = endpoint[:-len('/chat/completions')]
        if endpoint.endswith('/models'):
            return endpoint
        return f'{endpoint}/models'

    @api.model
    def _ai_extract_model_values(self, response_data):
        data = response_data.get('data') if isinstance(response_data, dict) else response_data
        if not isinstance(data, list):
            return []

        model_values = []
        seen_model_ids = set()
        for item in data:
            if isinstance(item, str):
                model_id = item
                name = item
            elif isinstance(item, dict):
                model_id = item.get('id') or item.get('model') or item.get('name')
                name = item.get('name') or item.get('display_name') or model_id
            else:
                continue

            model_id = str(model_id or '').strip()
            if not model_id or model_id in seen_model_ids:
                continue
            seen_model_ids.add(model_id)
            model_values.append({
                'model_id': model_id,
                'name': str(name or model_id).strip() or model_id,
            })
        return model_values

    def action_ai_load_models(self):
        self.ensure_one()
        endpoint = (self.ai_endpoint or '').strip()
        api_key = (self.ai_api_key or '').strip()
        if not endpoint:
            raise UserError(_('Set an AI Base URL before loading models.'))
        if not api_key:
            raise UserError(_('Set an AI API Key before loading models.'))

        try:
            response = requests.get(
                self._ai_models_url(endpoint),
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=15,
            )
            response.raise_for_status()
            model_values = self._ai_extract_model_values(response.json())
        except (ValueError, requests.RequestException) as error:
            raise UserError(_('Unable to load AI models: %s', error)) from error

        if not model_values:
            raise UserError(_('No AI models were returned by this provider.'))

        provider = self.ai_provider or 'openrouter'
        endpoint = endpoint.rstrip('/')
        self._set_ai_model_cache(provider, endpoint, model_values)
        returned_model_ids = [model_value['model_id'] for model_value in model_values]
        selected_model = self.ai_model if self.ai_model in returned_model_ids else returned_model_ids[0]
        self.ai_model = selected_model
        self.ai_model_id = selected_model
        for profile, meta in AI_MODEL_PROFILES.items():
            if profile == 'default':
                continue
            current_model = (self[meta['field']] or '').strip()
            if current_model in returned_model_ids:
                self[meta['selection_field']] = current_model
        self._set_ai_settings_values()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Loaded %s AI models.', len(returned_model_ids)),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    # NOTE: These fields depend on the context, if we want them to be computed
    # we have to make them depend on a field. This is because we are on a TransientModel.
    @api.depends('company_id')
    def _compute_company_count(self):
        company_count = self.env['res.company'].sudo().search_count([])
        for record in self:
            record.company_count = company_count

    @api.depends('company_id')
    def _compute_active_user_count(self):
        active_user_count = self.env['res.users'].sudo().search_count([('share', '=', False)])
        for record in self:
            record.active_user_count = active_user_count

    @api.depends('company_id')
    def _compute_language_count(self):
        language_count = len(self.env['res.lang'].get_installed())
        for record in self:
            record.language_count = language_count

    @api.depends('company_id')
    def _compute_company_informations(self):
        informations = '%s\n' % self.company_id.street if self.company_id.street else ''
        informations += '%s\n' % self.company_id.street2 if self.company_id.street2 else ''
        informations += '%s' % self.company_id.zip if self.company_id.zip else ''
        informations += '\n' if self.company_id.zip and not self.company_id.city else ''
        informations += ' - ' if self.company_id.zip and self.company_id.city else ''
        informations += '%s\n' % self.company_id.city if self.company_id.city else ''
        informations += '%s\n' % self.company_id.state_id.display_name if self.company_id.state_id else ''
        informations += '%s' % self.company_id.country_id.display_name if self.company_id.country_id else ''
        vat_display = self.company_id.country_id.vat_label or _('VAT')
        vat_display = '\n' + vat_display + ': '
        informations += '%s %s' % (vat_display, self.company_id.vat) if self.company_id.vat else ''

        for record in self:
            record.company_informations = informations

    @api.depends('company_id')
    def _compute_is_root_company(self):
        for record in self:
            record.is_root_company = not record.company_id.parent_id
