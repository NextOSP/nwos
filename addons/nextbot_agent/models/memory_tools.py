# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import logging

from nwos import models

_logger = logging.getLogger(__name__)


class NextBotToolRegistry(models.AbstractModel):
    """Memory and knowledge tools for NextBot.

    remember/forget are classified as read tools (no approval) on purpose:
    they only write to the caller's own user-scoped memory rows, which the
    user can inspect and edit in the workspace at any time, content is capped
    at 500 characters with per-run and per-user limits, and rows are archived
    rather than deleted. This is a documented exception for the assistant's
    own memory store — NOT a change to the rule that ERP data writes always
    require approval.
    """

    _inherit = 'nextbot.tool.registry'

    def _get_tool_providers(self):
        providers = super()._get_tool_providers()
        providers.update({
            'remember': {
                'definition': {
                    'type': 'function',
                    'function': {
                        'name': 'remember',
                        'description': (
                            'Save one short durable fact or preference the user stated about '
                            'themselves (role, standing needs, formatting or language '
                            'preferences). Never store secrets, credentials, or one-off task '
                            'details.'
                        ),
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'content': {
                                    'type': 'string',
                                    'description': "The fact, in the user's language, max 500 characters.",
                                },
                            },
                            'required': ['content'],
                        },
                    },
                },
                'access': 'read',
                'executor': '_execute_memory_remember',
                'card_type': 'tool_result',
            },
            'forget': {
                'definition': {
                    'type': 'function',
                    'function': {
                        'name': 'forget',
                        'description': 'Archive the stored user memory that best matches the query.',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string'},
                            },
                            'required': ['query'],
                        },
                    },
                },
                'access': 'read',
                'executor': '_execute_memory_forget',
                'card_type': 'tool_result',
            },
            'search_memory': {
                'definition': {
                    'type': 'function',
                    'function': {
                        'name': 'search_memory',
                        'description': "Search the current user's stored memories.",
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string'},
                                'limit': {'type': 'integer', 'minimum': 1, 'maximum': 10},
                            },
                            'required': ['query'],
                        },
                    },
                },
                'access': 'read',
                'executor': '_execute_memory_search',
                'card_type': 'tool_result',
            },
            'search_documents': {
                'definition': {
                    'type': 'function',
                    'function': {
                        'name': 'search_documents',
                        'description': (
                            'Search the indexed organization knowledge documents and the files '
                            'uploaded to this conversation, returning the most relevant excerpts.'
                        ),
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string'},
                                'limit': {'type': 'integer', 'minimum': 1, 'maximum': 10},
                            },
                            'required': ['query'],
                        },
                    },
                },
                'access': 'read',
                'executor': '_execute_document_search',
                'card_type': 'tool_result',
            },
        })
        return providers

    def _execute_memory_remember(self, tool_name, arguments, run):
        Memory = self.env['nextbot.memory']
        if not Memory._memory_enabled():
            return {'saved': False, 'reason': 'memory_disabled'}
        content = Memory._clean_content(arguments.get('content'))
        if not content:
            return {'saved': False, 'reason': 'empty'}
        if Memory._looks_sensitive(content):
            return {'saved': False, 'reason': 'sensitive_content_refused'}
        if run and run.sudo().remember_call_count >= 3:
            return {'saved': False, 'reason': 'rate_limited'}
        if run:
            run.sudo().remember_call_count += 1
        record, created = Memory._save_candidate(self.env.user, content, 'tool', run=run)
        if created:
            return {'saved': True, 'memory_id': record.id, 'content': record.content}
        if record:
            return {'saved': False, 'reason': 'duplicate', 'memory_id': record.id}
        return {'saved': False, 'reason': 'cap_reached'}

    def _execute_memory_forget(self, tool_name, arguments, run):
        matches = self.env['nextbot.retrieval']._search_memories(
            self.env.user, arguments.get('query'), limit=1, min_score=0.45,
        )
        if not matches:
            return {'found': False}
        memory = self.env['nextbot.memory'].browse(matches[0]['id'])
        memory.write({'active': False})
        return {'found': True, 'forgotten': matches[0]['content']}

    def _execute_memory_search(self, tool_name, arguments, run):
        limit = min(max(int(arguments.get('limit') or 5), 1), 10)
        matches = self.env['nextbot.retrieval']._search_memories(
            self.env.user, arguments.get('query'), limit=limit,
        )
        return {'memories': [
            {'content': match['content'], 'source': match['source']}
            for match in matches
        ]}

    def _execute_document_search(self, tool_name, arguments, run):
        channel = run.conversation_id.channel_id if run else None
        try:
            self.env['nextbot.knowledge.chunk']._ensure_channel_attachments(channel)
        except Exception:  # noqa: BLE001 - lazy chunking is best-effort
            _logger.warning('NextBot channel chunking failed', exc_info=True)
        limit = min(max(int(arguments.get('limit') or 5), 1), 10)
        matches = self.env['nextbot.retrieval']._search_chunks(
            arguments.get('query'), channel=channel, limit=limit,
        )
        return {'excerpts': [
            {'source': match['name'], 'part': match['part'], 'content': match['content']}
            for match in matches
        ]}
