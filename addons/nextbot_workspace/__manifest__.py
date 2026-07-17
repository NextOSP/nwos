# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    "name": "NextBot Workspace",
    "version": "2.0.0",
    "category": "Productivity/Discuss",
    "summary": "Dedicated IBM Carbon AI workspace for NextBot",
    "description": """
NextBot Workspace
=================
A dedicated, responsive OWL workspace for NextBot with durable task plans,
streaming responses, structured result cards, approval controls, attachments, and a safe activity
inspector. The interface uses the local IBM Carbon token and typography layer;
it does not add a second frontend runtime or load remote assets.
""",
    "author": "NextOSP",
    "website": "https://github.com/NextOSP",
    "depends": ["nextbot_agent", "web", "web_carbon"],
    "data": [
        "data/nextbot_workspace_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "nextbot_workspace/static/src/**/*.js",
            "nextbot_workspace/static/src/**/*.xml",
            "nextbot_workspace/static/src/**/*.scss",
        ],
        "web.assets_unit_tests": [
            "nextbot_workspace/static/tests/**/*.test.js",
        ],
    },
    "application": True,
    "installable": True,
    # Part of the standard NWOS install: follows nextbot_agent automatically.
    "auto_install": ["nextbot_agent"],
    "license": "LGPL-3",
}
