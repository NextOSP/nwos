{
    'name': 'Web Carbon Theme',
    'version': '1.0',
    'category': 'Hidden/Themes',
    'summary': 'IBM Carbon Design System theme for the backend and frontend',
    'description': """
Web Carbon Theme
================
Restyles the whole web client (backend, login, portal and website) to follow
the IBM Carbon Design System: Carbon color tokens, IBM Plex typography, the
2x/8px spacing grid, sharp (0px) corners, WCAG-AA contrast pairs, a distinctive
Blue 60 focus ring, and the dark Gray-100 UI Shell.

Everything is token-driven: colors, type and spacing come from a single token
layer (`scss/tokens/carbon_tokens.scss`). See `CARBON_DESIGN.md` for the design
principles. This addon only prepends variable overrides and adds component SCSS;
it does not modify any core file, so it can be installed or removed cleanly.
""",
    'author': 'NextOSP',
    # Depend on web_nwos (the auto-installed legacy NWOS theme) so web_carbon's
    # assets load AFTER it in every bundle and win the cascade.
    'depends': ['web', 'web_nwos'],
    'auto_install': False,
    'data': [
        'views/login_templates.xml',
    ],
    'assets': {
        # --- Variable layer (loaded before web's, wins via !default) -----------
        # NOTE: each ('prepend', ...) inserts at the front of the bundle, so the
        # entries are listed in REVERSE of the desired compile order. Final order
        # becomes: carbon_tokens -> primary_variables -> navbar.variables ->
        # frontend/primary_variables -> (web's own variable files).
        'web._assets_primary_variables': [
            ('prepend', 'web_carbon/static/src/scss/frontend/primary_variables.scss'),
            ('prepend', 'web_carbon/static/src/webclient/navbar/navbar.variables.scss'),
            ('prepend', 'web_carbon/static/src/scss/primary_variables.scss'),
            ('prepend', 'web_carbon/static/src/scss/tokens/carbon_tokens.scss'),
        ],
        'web._assets_secondary_variables': [
            ('prepend', 'web_carbon/static/src/scss/secondary_variables.scss'),
        ],
        # --- Backend components ------------------------------------------------
        'web.assets_backend': [
            'web_carbon/static/src/scss/fonts.scss',
            'web_carbon/static/src/scss/components/base.scss',
            'web_carbon/static/src/scss/components/layout.scss',
            'web_carbon/static/src/scss/components/shell.scss',
            'web_carbon/static/src/scss/components/home_menu.scss',
            'web_carbon/static/src/scss/components/buttons.scss',
            'web_carbon/static/src/scss/components/fields.scss',
            'web_carbon/static/src/scss/components/ai.scss',
            'web_carbon/static/src/scss/components/controls.scss',
            'web_carbon/static/src/scss/components/dropdown.scss',
            'web_carbon/static/src/scss/components/switch_company.scss',
            'web_carbon/static/src/scss/components/modal.scss',
            'web_carbon/static/src/scss/components/table.scss',
            'web_carbon/static/src/scss/components/tags.scss',
            'web_carbon/static/src/scss/components/notification.scss',
            'web_carbon/static/src/scss/components/discuss.scss',
            'web_carbon/static/src/scss/components/breadcrumb.scss',
            'web_carbon/static/src/scss/components/tabs.scss',
            'web_carbon/static/src/scss/components/pagination.scss',
            'web_carbon/static/src/scss/components/kanban.scss',
            'web_carbon/static/src/scss/components/calendar.scss',
            'web_carbon/static/src/scss/components/settings.scss',
            # JS: stretch autocomplete/combobox menus to the full field width.
            'web_carbon/static/src/webclient/autocomplete/autocomplete_carbon.js',
            # JS: right-align own chat messages everywhere (not just chat windows).
            'web_carbon/static/src/webclient/discuss/message_patch.js',
            # JS: drop the "My NWOS.com account" entry from the user menu.
            'web_carbon/static/src/webclient/user_menu/remove_account_item.js',

            # JS+XML: add a "view in full" expand button to act_window target=new dialogs.
            'web_carbon/static/src/webclient/action_dialog/action_dialog_expand.js',
            'web_carbon/static/src/webclient/action_dialog/action_dialog_expand.xml',
        ],
        # --- Frontend (login, portal, website) ---------------------------------
        'web.assets_frontend': [
            'web_carbon/static/src/scss/fonts.scss',
            'web_carbon/static/src/scss/frontend/frontend.scss',
            'web_carbon/static/src/scss/frontend/portal.scss',
        ],
        # --- Reports (PDF/HTML previews) --------------------------------------
        'web.report_assets_common': [
            'web_carbon/static/src/scss/fonts.scss',
            'web_carbon/static/src/scss/report/report.scss',
        ],
    },
    'license': 'LGPL-3',
}
