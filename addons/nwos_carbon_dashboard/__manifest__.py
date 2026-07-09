# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Carbon Dashboards',
    'version': '1.0',
    'category': 'Productivity/Dashboard',
    'author': 'NextOSP',
    'summary': 'Render the spreadsheet dashboards in IBM Carbon style with @carbon/charts',
    'description': """
Carbon Dashboards
=================
Overrides the spreadsheet dashboard client action (path ``dashboards``) with a
generic OWL renderer that draws every published dashboard in the IBM Carbon
Design System: IBM Plex typography, sharp corners, the Carbon categorical
palette and real ``@carbon/charts`` charts.

The o-spreadsheet ``Model`` is reused purely as a data/formula engine — its
figure/chart/scorecard/list getters feed our Carbon components; the spreadsheet
canvas is never rendered. Same URL, menu and sidebar as the original action.
""",
    # spreadsheet_dashboard => our action override loads after theirs and wins.
    # web_carbon           => Carbon SCSS token layer ($carbon-*) + IBM Plex fonts.
    'depends': ['spreadsheet_dashboard', 'web_carbon'],
    'data': [
        'data/manufacturing_dashboard.xml',
    ],
    'assets': {
        # Vendored @carbon/charts (UMD, global `Charts`, d3 bundled in) + its CSS.
        # Lazy bundle: only fetched when a dashboard is actually opened.
        'nwos_carbon_dashboard.carbon_charts_lib': [
            'nwos_carbon_dashboard/static/lib/carbon-charts/charts.umd.js',
            'nwos_carbon_dashboard/static/lib/carbon-charts/styles.min.css',
        ],
        # The dashboard action + its components import from @spreadsheet* which
        # only exist in the lazy o_spreadsheet bundle, and our action override
        # must register AFTER spreadsheet_dashboard's (same bundle, later module
        # in the dependency order => our `add(force:true)` wins).
        'spreadsheet.o_spreadsheet': [
            'nwos_carbon_dashboard/static/src/**/*.js',
            'nwos_carbon_dashboard/static/src/**/*.xml',
        ],
        # SCSS lives in the backend bundle where web_carbon's $carbon-* token
        # variables are in scope.
        'web.assets_backend': [
            'nwos_carbon_dashboard/static/src/**/*.scss',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
