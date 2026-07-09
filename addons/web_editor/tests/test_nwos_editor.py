# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import nwos.tests

@nwos.tests.tagged("post_install", "-at_install")
class TestNWOSEditor(nwos.tests.HttpCase):

    def test_nwos_editor_suite(self):
        self.browser_js('/web_editor/tests', "", "", login='admin', timeout=1800)
