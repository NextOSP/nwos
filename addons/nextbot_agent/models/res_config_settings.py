# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    nextbot_approval_ttl_minutes = fields.Integer(
        string='Approval lifetime (minutes)', default=1440,
        config_parameter='nextbot_agent.approval_ttl_minutes',
        groups='base.group_system',
    )
    nextbot_max_tool_calls = fields.Integer(
        string='Maximum tool calls per run', default=100,
        config_parameter='nextbot_agent.max_tool_calls',
        groups='base.group_system',
    )
    nextbot_max_model_calls = fields.Integer(
        string='Maximum model calls per run', default=50,
        config_parameter='nextbot_agent.max_model_calls',
        groups='base.group_system',
    )
    nextbot_max_iterations = fields.Integer(
        string='Maximum coordinator iterations', default=40,
        config_parameter='nextbot_agent.max_iterations',
        groups='base.group_system',
    )
    nextbot_max_step_tool_calls = fields.Integer(
        string='Maximum tool calls per read step', default=12,
        config_parameter='nextbot_agent.max_step_tool_calls',
        groups='base.group_system',
    )
    nextbot_context_token_budget = fields.Integer(
        string='Context token budget', default=48000,
        config_parameter='nextbot_agent.context_token_budget',
        groups='base.group_system',
    )
    nextbot_attachment_count_limit = fields.Integer(
        string='Maximum attachments per message', default=5,
        config_parameter='nextbot_agent.attachment_count_limit',
        groups='base.group_system',
    )
    nextbot_attachment_size_limit_mb = fields.Integer(
        string='Maximum attachment size (MB)', default=20,
        config_parameter='nextbot_agent.attachment_size_limit_mb',
        groups='base.group_system',
    )
    nextbot_prompt_character_limit = fields.Integer(
        string='Maximum prompt length', default=20000,
        config_parameter='nextbot_agent.prompt_character_limit',
        groups='base.group_system',
    )
    nextbot_force_response_lang = fields.Selection(
        lambda self: self.env['res.lang'].get_installed(),
        string='Force response language',
        config_parameter='nextbot_agent.force_response_lang',
        groups='base.group_system',
        help="Leave empty to answer each user in their own interface language.",
    )
    nextbot_memory_enabled = fields.Boolean(
        string='User memory', default=True,
        config_parameter='nextbot_agent.memory_enabled',
        groups='base.group_system',
    )
    nextbot_auto_learn_enabled = fields.Boolean(
        string='Learn from chats', default=True,
        config_parameter='nextbot_agent.auto_learn_enabled',
        groups='base.group_system',
    )
    nextbot_memory_max_per_user = fields.Integer(
        string='Maximum memories per user', default=200,
        config_parameter='nextbot_agent.memory_max_per_user',
        groups='base.group_system',
    )
