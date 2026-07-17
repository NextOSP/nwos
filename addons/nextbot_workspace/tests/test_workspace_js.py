# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.tests import HttpCase, tagged


def _unit_test_error_checker(message):
    return '[HOOT]' not in message


@tagged('post_install', '-at_install', 'nextbot_workspace')
class TestNextBotWorkspaceJS(HttpCase):

    def test_workspace_unit_suite(self):
        self.browser_js(
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&id=4884b7ca',
            '',
            '',
            login='admin',
            timeout=300,
            success_signal='[HOOT] Test suite succeeded',
            error_checker=_unit_test_error_checker,
        )
