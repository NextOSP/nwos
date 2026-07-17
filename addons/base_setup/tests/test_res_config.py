# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from nwos.exceptions import UserError
from nwos.tests.common import TransactionCase


def just_raise(*args):
    raise Exception("We should not be here.")


class TestResConfig(TransactionCase):

    def setUp(self):
        super(TestResConfig, self).setUp()

        self.user = self.env.ref('base.user_admin')
        self.company = self.env['res.company'].create({'name': 'oobO'})
        self.user.write({'company_ids': [(4, self.company.id)], 'company_id': self.company.id})
        Settings = self.env['res.config.settings'].with_user(self.user.id)
        self.config = Settings.create({})

    def test_multi_company_res_config_group(self):
        # Enable/Disable a group in a multi-company environment
        # 1/ All the users should be added/removed from the group
        # and not only the users of the allowed companies
        # 2/ The changes should be reflected for new users (Default User Template)

        company = self.env['res.company'].create({'name': 'My Last Company'})
        partner = self.env['res.partner'].create({
            'name': 'My User'
        })
        user = self.env['res.users'].create({
            'login': 'My User',
            'company_id': company.id,
            'company_ids': [(4, company.id)],
            'partner_id': partner.id,
        })

        ResConfig = self.env['res.config.settings']
        default_values = ResConfig.default_get(list(ResConfig.fields_get()))

        # Case 1: Enable a group
        default_values.update({'group_multi_currency': True})
        ResConfig.create(default_values).execute()
        self.assertTrue(user in self.env.ref('base.group_multi_currency').sudo().all_user_ids)

        new_partner = self.env['res.partner'].create({'name': 'New User'})
        new_user = self.env['res.users'].create({
            'login': 'My First New User',
            'company_id': company.id,
            'company_ids': [(4, company.id)],
            'partner_id': new_partner.id,
        })
        self.assertTrue(new_user in self.env.ref('base.group_multi_currency').sudo().all_user_ids)

        # Case 2: Disable a group
        default_values.update({'group_multi_currency': False})
        ResConfig.create(default_values).execute()
        self.assertTrue(user not in self.env.ref('base.group_multi_currency').sudo().all_user_ids)

        new_partner = self.env['res.partner'].create({'name': 'New User'})
        new_user = self.env['res.users'].create({
            'login': 'My Second New User',
            'company_id': company.id,
            'company_ids': [(4, company.id)],
            'partner_id': new_partner.id,
        })
        self.assertTrue(new_user not in self.env.ref('base.group_multi_currency').sudo().all_user_ids)

    def test_no_install(self):
        """Make sure that when saving settings,
           no modules are installed if nothing was set to install.
        """
        # check that no module should be installed in the first place
        config_fields = self.config._get_classified_fields()
        for module in config_fields['module']:
            if self.config[f'module_{module.name}']:
                self.assertTrue(module.state != 'uninstalled',
                                "All set modules should already be installed.")
        # if we try to install something, raise; so nothing should be installed
        with patch('nwos.addons.base.models.ir_module.IrModuleModule.button_immediate_install', new=just_raise):
            self.config.execute()

    def test_install(self):
        """Make sure that the previous test is valid, i.e. when saving settings,
           it starts module install if something was set to install.
        """
        config_fields = self.config._get_classified_fields()
        # set the first uninstalled module to install
        module_to_install = next(m for m in config_fields['module'] if m.state == 'uninstalled')
        self.config[f'module_{module_to_install.name}'] = True

        with patch('nwos.addons.base.models.ir_module.IrModuleModule.button_immediate_install', new=just_raise):
            with self.assertRaisesRegex(Exception, "We should not be here."):
                self.config.execute()

    def test_ai_settings_fallback_to_legacy_crm_parameters(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.search([('key', 'in', [
            'base.ai.enabled',
            'base.ai.provider',
            'base.ai.endpoint',
            'base.ai.model',
            'base.ai.api_key',
        ])]).unlink()
        ICP.set_param('crm.ai_lead_scoring.enabled', True)
        ICP.set_param('crm.ai_lead_scoring.provider', 'openrouter')
        ICP.set_param('crm.ai_lead_scoring.endpoint', 'https://openrouter.ai/api/v1')
        ICP.set_param('crm.ai_lead_scoring.model', 'openai/gpt-4o-mini')
        ICP.set_param('crm.ai_lead_scoring.api_key', 'legacy-key')

        values = self.env['res.config.settings'].default_get([
            'ai_enabled',
            'ai_provider',
            'ai_endpoint',
            'ai_model',
            'ai_api_key',
        ])

        self.assertTrue(values['ai_enabled'])
        self.assertEqual('openrouter', values['ai_provider'])
        self.assertEqual('https://openrouter.ai/api/v1', values['ai_endpoint'])
        self.assertEqual('openai/gpt-4o-mini', values['ai_model'])
        self.assertEqual('legacy-key', values['ai_api_key'])

    def test_ai_settings_default_model_is_available_without_cache(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.search([('key', 'in', [
            'base.ai.model_list',
            'base.ai.enabled',
            'base.ai.provider',
            'base.ai.endpoint',
            'base.ai.model',
            'base.ai.api_key',
        ])]).unlink()

        values = self.env['res.config.settings'].default_get([
            'ai_enabled',
            'ai_provider',
            'ai_endpoint',
            'ai_model',
            'ai_model_id',
        ])

        self.assertFalse(values['ai_enabled'])
        self.assertEqual('openrouter', values['ai_provider'])
        self.assertEqual('https://openrouter.ai/api/v1', values['ai_endpoint'])
        self.assertEqual('openai/gpt-5.6-terra', values['ai_model'])
        self.assertEqual('openai/gpt-5.6-terra', values['ai_model_id'])

        selection = self.env['res.config.settings']._get_ai_model_selection()
        self.assertIn(('openai/gpt-5.6-terra', 'openai/gpt-5.6-terra'), selection)

    def test_ai_load_models(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('base.ai.model_list', '{}')
        settings = self.env['res.config.settings'].create({
            'ai_enabled': True,
            'ai_provider': 'openai',
            'ai_endpoint': 'https://api.openai.com/v1',
            'ai_api_key': 'test-key',
        })

        with patch('nwos.addons.base_setup.models.res_config_settings.requests.get') as mock_get:
            mock_response = mock_get.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                'data': [
                    {'id': 'gpt-4o-mini', 'name': 'GPT-4o mini'},
                    {'id': 'gpt-4.1'},
                    {'id': 'gpt-4o-mini'},
                ],
            }

            action = settings.action_ai_load_models()

        self.assertEqual('display_notification', action['tag'])
        self.assertEqual('https://api.openai.com/v1/models', mock_get.call_args.args[0])
        self.assertEqual('Bearer test-key', mock_get.call_args.kwargs['headers']['Authorization'])
        self.assertEqual('gpt-4o-mini', settings.ai_model)
        self.assertEqual('gpt-4o-mini', settings.ai_model_id)
        self.assertEqual('gpt-4o-mini', ICP.get_param('base.ai.model'))

        model_cache = settings._get_ai_model_cache()
        self.assertEqual(
            ['gpt-4o-mini', 'gpt-4.1'],
            [model['model_id'] for model in model_cache['openai|https://api.openai.com/v1']],
        )

    def test_ai_load_models_requires_credentials(self):
        settings = self.env['res.config.settings'].create({
            'ai_provider': 'openai',
            'ai_endpoint': 'https://api.openai.com/v1',
        })
        with self.assertRaises(UserError):
            settings.action_ai_load_models()
