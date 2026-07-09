{
    "name": "NWOS Core Backend",
    "category": "Hidden",
    "version": "3.0",
    "author": "NextOSP",
    "website": "https://github.com/NextOSP",
    'company': 'NextOSP.',
    "depends": ['base', 'web'],
    'auto_install': True,
    "data": [
        # 'views/style.xml',
        'data/theme_config.xml',
        'data/ir_config_param_data.xml',
        # 'views/sidebar.xml',  # NWOS19: injects orphaned f_launcher/sidebar DOM (broken on NWOS 19); disabled
        'views/web.xml',
        'views/res_config_settings.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'web_nwos/static/src/scss/login.scss',
        ],
        'web.assets_backend': [
            # NWOS 4.0: branding only. The legacy web_nwos backend theme
            # (SCSS/JS built for NWOS <=13 DOM) mis-styles NWOS 19's redesigned
            # web client (tiny inputs, stray preloader "droplet", broken nav),
            # so it is disabled; NWOS 19 native UI + NWOS brand color is used.
            'web_nwos/static/src/scss/theme_primary_variables.scss',
            # Branding only: font (fonts.scss @font-face loads Rubik that
            # variables.scss sets as the root font-family) + the blue navbar.
            # The heavy DOM-styling files (fields_extra/form_view_extra/style/
            # preloader/sidebar) stay disabled.
            'web_nwos/static/src/scss/fonts.scss',
            'web_nwos/static/src/scss/theme/navbar.scss',
            'web_nwos/static/src/scss/control_panel.scss',
        ],
        # NWOS19: web.assets_qweb bundle no longer exists; its templates
        # (menu.xml, backend_theme_customizer.xml) are already loaded via
        # web.assets_backend above.

        'web._assets_bootstrap': [
            'web_nwos/static/src/scss/theme_primary_variables.scss',
            'web_nwos/static/src/scss/variables.scss',
        ],

        'web._assets_helpers': [
            'web_nwos/static/src/scss/variables.scss',
         ],

        'web._assets_primary_variables': [
            # Set NWOS blue BEFORE NWOS's primary_variables so the whole
            # brand-color cascade (navbar, buttons, badges, filters) is blue.
            ('before', 'web/static/src/scss/primary_variables.scss',
             'web_nwos/static/src/scss/nwos_brand_primary.scss'),
            '/web_nwos/static/src/scss/backend_theme_customizer/colors.scss',
            'web_nwos/static/src/scss/color_palettes.scss',
        ],
        # NWOS19: point_of_sale.assets form_view_extra.scss used removed
        # $o-brand-* context (Undefined variable warning); disabled.


    },
    "license": "LGPL-3",
    "uninstall_hook": "_uninstall_reset_changes",
}
