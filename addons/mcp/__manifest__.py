# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    "name": "Model Context Protocol (MCP) Gateway",
    "summary": "Secure, generic MCP access to every installed business model",
    "version": "1.0",
    "category": "Administration/Administration",
    "author": "NextOSP",
    "website": "https://nextosp.com",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail"],
    "data": [
        "security/mcp_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/mcp_policy_views.xml",
        "views/mcp_audit_views.xml",
        "views/mcp_token_views.xml",
        "wizards/mcp_connection_views.xml",
        "views/res_config_settings_views.xml",
        "views/mcp_menus.xml",
    ],
    "application": True,
    "installable": True,
}
