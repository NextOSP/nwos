# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'Online Task Submission',
    'category': 'Website/Website',
    'summary': 'Add a task suggestion form to your website',
    'version': '1.0',
    'description': """
Generate tasks in Project app from a form published on your website. This module requires the use of the *Form Builder* module (available in NWOS Enterprise) in order to build the form.
    """,
    # NWOS19: fully merged into standard `website_project` (same website_form_key,
    # whitelist, portal templates and editor JS). Keeping it installable causes a
    # duplicate `website_portal_my_task` xpath conflict, so it is disabled.
    'installable': False,
    'depends': ['website', 'project'],
    'data': [
        'data/website_form_project_data.xml',
        'views/project_portal_project_task_template.xml',
        'views/project_portal_project_project_template.xml',
        ],
    'auto_install': False,
    'assets': {
        'website.assets_wysiwyg': [
            'website_form_project/static/src/js/website_form_project_editor.js',
        ],
        'project.webclient': [
            # In website, there is a patch of the LinkDialog (see
            # website/static/src/js/editor/editor.js) that require the utils.js.
            # Thus, when website is installed, this bundle need to have the
            # utils.js in its assets, otherwise, there will be an unmet
            # dependency.
            'website/static/src/js/utils.js',
            'web/static/src/core/autocomplete/*',
            'website/static/src/components/autocomplete_with_pages/*',
        ],
    },
    'license': 'LGPL-3',
}
