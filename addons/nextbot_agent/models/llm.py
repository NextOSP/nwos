# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models


class NextBotLLM(models.AbstractModel):
    """Provider-neutral facade used by the v2 runtime.

    The first adapter deliberately delegates transport and provider quirks to
    ``mail.bot``.  Keeping the orchestration code behind this facade prevents
    the task engine from depending on the legacy chatbot loop or prompt.
    """

    _name = 'nextbot.llm'
    _description = 'NextBot LLM Provider Adapter'

    def settings(self, profile='intelligent'):
        return self.env['mail.bot']._ai_get_settings(profile=profile)

    def configuration_error(self, settings):
        return self.env['mail.bot']._ai_configuration_error(settings)

    def complete(
        self, settings, messages, tools=None, tool_choice=None,
        on_delta=None, should_stop=None,
    ):
        return self.env['mail.bot']._ai_chat_completion(
            settings,
            messages,
            tools=tools,
            tool_choice=tool_choice,
            on_delta=on_delta,
            should_stop=should_stop,
        )

    def parse_tool_call(self, tool_call):
        return self.env['mail.bot']._ai_parse_tool_call(tool_call)

    def plain_content(self, content):
        return self.env['mail.bot']._ai_plain_ai_content(content)

