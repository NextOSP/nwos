# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from nwos.exceptions import AccessDenied
from nwos.tests.common import TransactionCase


class TestAuthOAuth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['auth.oauth.provider'].create({
            'name': 'Test OAuth Provider',
            'auth_endpoint': 'https://accounts.example.com/oauth2/auth',
            'validation_endpoint': 'https://accounts.example.com/oauth2/tokeninfo',
            'body': 'Sign in with Example',
            'enabled': True,
        })

    def test_odoo_provider_is_not_installed(self):
        self.assertFalse(
            self.env.ref('auth_oauth.provider_openerp', raise_if_not_found=False)
        )
        self.assertFalse(self.env['auth.oauth.provider'].search([
            ('auth_endpoint', '=', 'https://accounts.odoo.com/oauth2/auth'),
        ]))

    def test_disabled_provider_cannot_validate_token(self):
        self.provider.enabled = False
        users = self.env['res.users']

        with patch.object(type(users), '_auth_oauth_rpc') as oauth_rpc:
            with self.assertRaises(AccessDenied):
                users._auth_oauth_validate(self.provider.id, 'access-token')

        oauth_rpc.assert_not_called()

    def test_disabled_provider_cannot_authenticate_stored_token(self):
        user = self.env.ref('base.user_admin')
        user.write({
            'oauth_provider_id': self.provider.id,
            'oauth_uid': 'oauth-test-user',
            'oauth_access_token': 'access-token',
        })
        credential = {
            'login': user.login,
            'token': 'access-token',
            'type': 'oauth_token',
        }
        oauth_user = user.with_user(user)

        auth_info = oauth_user._check_credentials(credential, {'interactive': True})
        self.assertEqual(auth_info['uid'], user.id)

        self.provider.enabled = False
        with self.assertRaises(AccessDenied):
            oauth_user._check_credentials(credential, {'interactive': True})
