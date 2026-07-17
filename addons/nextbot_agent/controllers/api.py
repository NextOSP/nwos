# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import base64
import binascii
import os

from nwos import _, http
from nwos.exceptions import AccessError, UserError, ValidationError
from nwos.http import request
from nwos.tools import html2plaintext

from ..utils import iso_utc


ALLOWED_ATTACHMENT_MIMETYPES = {
    'application/csv',
    'application/json',
    'application/msword',
    'application/pdf',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/xml',
    'image/gif',
    'image/jpeg',
    'image/png',
    'image/webp',
    'text/csv',
    'text/markdown',
    'text/plain',
    'text/xml',
}


class NextBotAgentController(http.Controller):

    def _conversation(self, conversation_id, include_archived=True):
        Conversation = request.env['nextbot.conversation']
        if include_archived:
            Conversation = Conversation.with_context(active_test=False)
        conversation = Conversation.search([
            ('id', '=', int(conversation_id or 0)),
            ('user_id', '=', request.env.user.id),
        ], limit=1)
        if not conversation:
            raise AccessError(_('NextBot conversation not found or not accessible.'))
        conversation._ensure_current_user()
        return conversation

    def _run(self, run_id):
        run = request.env['nextbot.run'].search([
            ('id', '=', int(run_id or 0)),
            ('user_id', '=', request.env.user.id),
        ], limit=1)
        if not run:
            raise AccessError(_('NextBot run not found or not accessible.'))
        run._ensure_current_user()
        return run

    def _approval(self, approval_id):
        approval = request.env['nextbot.approval'].search([
            ('id', '=', int(approval_id or 0)),
            ('user_id', '=', request.env.user.id),
        ], limit=1)
        if not approval:
            raise AccessError(_('NextBot approval not found or not accessible.'))
        approval._ensure_current_user()
        return approval

    def _artifact(self, artifact_id):
        artifact = request.env['nextbot.artifact'].search([
            ('id', '=', int(artifact_id or 0)),
            ('user_id', '=', request.env.user.id),
        ], limit=1)
        if not artifact:
            raise AccessError(_('NextBot artifact not found or not accessible.'))
        artifact.run_id._ensure_current_user()
        return artifact

    @staticmethod
    def _config_int(key, default, minimum, maximum):
        raw = request.env['ir.config_parameter'].sudo().get_param(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return min(max(value, minimum), maximum)

    def _validate_run_attachments(self, conversation, attachment_ids):
        if not isinstance(attachment_ids or [], list):
            raise ValidationError(_('attachment_ids must be a list.'))
        ids = []
        for attachment_id in attachment_ids or []:
            try:
                attachment_id = int(attachment_id)
            except (TypeError, ValueError) as error:
                raise ValidationError(_('Invalid attachment identifier.')) from error
            if attachment_id not in ids:
                ids.append(attachment_id)
        max_count = self._config_int('nextbot_agent.attachment_count_limit', 5, 1, 20)
        if len(ids) > max_count:
            raise ValidationError(_('A NextBot message can contain at most %s attachments.', max_count))
        attachments = request.env['ir.attachment'].browse(ids).exists()
        if len(attachments) != len(ids):
            raise AccessError(_('One or more attachments do not exist.'))
        max_bytes = self._config_int(
            'nextbot_agent.attachment_size_limit_mb', 20, 1, 50,
        ) * 1024 * 1024
        for attachment in attachments:
            attachment.check_access('read')
            if attachment.res_model != 'discuss.channel' or attachment.res_id != conversation.channel_id.id:
                raise AccessError(_('Attachments must belong to the selected NextBot conversation.'))
            if attachment.file_size and attachment.file_size > max_bytes:
                raise ValidationError(_('Attachment %s exceeds the configured size limit.', attachment.name))
            clean_mimetype = str(attachment.mimetype or '').split(';', 1)[0].strip().lower()
            if clean_mimetype not in ALLOWED_ATTACHMENT_MIMETYPES:
                raise ValidationError(_('Attachment type %s is not allowed.', clean_mimetype or _('unknown')))
            raw = attachment.raw or b''
            if not raw or len(raw) > max_bytes:
                raise ValidationError(_('Attachment %s is empty or too large.', attachment.name))
            self._validate_magic(clean_mimetype, raw)
        return attachments

    def _enqueue_run(self, conversation, prompt, attachments, input_message=None):
        user = request.env.user
        if not conversation.run_ids and conversation.name in (
            'New conversation', request.env._('New conversation'),
        ):
            title = prompt.replace('\n', ' ').strip()[:80]
            if title:
                conversation.sudo().name = title
                if conversation.channel_id.channel_type == 'group':
                    conversation.channel_id.sudo().name = request.env._('NextBot: %s', title)
        run = request.env['nextbot.run'].sudo().create({
            'conversation_id': conversation.id,
            'company_id': request.env.company.id,
            'allowed_company_ids': [(6, 0, request.env.companies.ids)],
            'prompt': prompt,
            'attachment_ids': [(6, 0, attachments.ids)],
            'input_message_id': input_message.id if input_message else False,
        }).with_user(user).with_context(allowed_company_ids=request.env.companies.ids)
        # Persist the user side immediately. The scheduled worker posts exactly
        # one bot response using the same Discuss thread.
        if not input_message:
            run._post_user_message()
        run._add_event('run.status', {
            'status': 'queued',
            'message': _('Your request is queued.'),
        })
        conversation._touch(run=run)
        cron = request.env.ref(
            'nextbot_agent.ir_cron_process_nextbot_runs',
            raise_if_not_found=False,
        )
        if cron:
            cron.sudo()._trigger()
        else:
            # Installation/update fallback; normal operation is always queued.
            run._execute_runtime()
        return run

    def _serialize_message(self, message, run_by_message):
        bot_partner_id = request.env.ref('base.partner_root').id
        attachments = []
        for attachment in message.attachment_ids:
            try:
                attachment.check_access('read')
            except AccessError:
                continue
            attachments.append({
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype,
                'size': attachment.file_size or 0,
                'url': '/web/content/%s?download=true' % attachment.id,
            })
        run = run_by_message.get(message.id)
        structured_run = run and (
            run.response_message_id == message
            or not run.response_message_id and run.input_message_id == message
        )
        run_events = (
            run.event_ids.sorted('sequence')[-200:]
            if structured_run else request.env['nextbot.run.event']
        )
        approvals = [approval._serialize() for approval in run.approval_ids] if structured_run else []
        artifacts = [artifact._serialize() for artifact in run.artifact_ids] if structured_run else []
        result_cards = [
            event.payload.get('card')
            for event in run_events
            if event.event_type == 'tool.completed'
            and isinstance(event.payload, dict)
            and isinstance(event.payload.get('card'), dict)
        ]
        # Tool result cards already cover the files they generated; only list
        # an artifact separately when no result card points at the same file.
        result_card_urls = {
            card.get('download_url')
            for card in result_cards
            if isinstance(card, dict) and card.get('download_url')
        }
        cards = [
            {'type': 'approval', **approval}
            for approval in approvals
        ] + [
            {**artifact, 'artifact_type': artifact.get('type'), 'type': 'artifact'}
            for artifact in artifacts
            # Raw JSON tool dumps stay in the inspector's Artifacts tab; only
            # user-facing files (reports, documents) render as chat cards.
            if 'json' not in str(artifact.get('mimetype') or '')
            and artifact.get('download_url') not in result_card_urls
        ] + result_cards
        plain_text = html2plaintext(message.body or '')
        return {
            'id': message.id,
            'role': 'assistant' if message.author_id.id == bot_partner_id else 'user',
            'author': {
                'id': message.author_id.id,
                'name': message.author_id.display_name,
            } if message.author_id else False,
            'body': str(message.body or ''),
            'content': plain_text,
            'text': plain_text,
            'date': iso_utc(message.date),
            'attachments': attachments,
            'run_id': run.id if run else False,
            'run_status': run.status if run else False,
            'events': [event._serialize() for event in run_events],
            'approvals': approvals,
            'artifacts': artifacts,
            'cards': cards,
        }

    @http.route('/nextbot/bootstrap', type='jsonrpc', auth='user')
    def bootstrap(self):
        # Import the legacy direct chat once so its Discuss history appears in
        # the workspace alongside new private-group conversations.
        request.env['nextbot.conversation']._get_or_create_for_user(reactivate=False)
        conversations = request.env['nextbot.conversation'].search([
            ('user_id', '=', request.env.user.id),
        ], limit=100)
        return {
            'user': {
                'id': request.env.user.id,
                'name': request.env.user.display_name,
                'partner_id': request.env.user.partner_id.id,
            },
            'conversations': [conversation._serialize() for conversation in conversations],
            'tools': request.env['nextbot.tool.registry'].get_metadata(),
            'limits': {
                'attachment_count': self._config_int('nextbot_agent.attachment_count_limit', 5, 1, 20),
                'attachment_size_mb': self._config_int('nextbot_agent.attachment_size_limit_mb', 20, 1, 50),
                'max_tool_calls': self._config_int('nextbot_agent.max_tool_calls', 100, 1, 1000),
                'max_model_calls': self._config_int('nextbot_agent.max_model_calls', 50, 1, 500),
                'max_iterations': self._config_int('nextbot_agent.max_iterations', 40, 1, 500),
            },
            'features': {
                'event_transport': 'bus_push',
                'event_bus_notification': 'nextbot.run/event',
                'activity_summaries': True,
                'private_chain_of_thought': False,
                'approvals': True,
                'artifacts': True,
                'cancellation': 'cooperative',
                'runtime_version': 2,
                'durable_plans': True,
                'steering': True,
                'parallel_reads': 3,
                'grouped_approvals': True,
                'budget_continuation': True,
            },
        }

    @http.route('/nextbot/conversations', type='jsonrpc', auth='user')
    def conversations(self, create=False, name=None, search=None, query=None, archived=False, limit=50):
        if create or name is not None:
            conversation = request.env['nextbot.conversation']._create_for_user(name=name)
            return {'conversation': conversation._serialize()}
        limit = min(max(int(limit or 50), 1), 100)
        domain = [('user_id', '=', request.env.user.id)]
        Conversation = request.env['nextbot.conversation']
        if archived:
            Conversation = Conversation.with_context(active_test=False)
        else:
            domain.append(('active', '=', True))
        search = search if search is not None else query
        if search and str(search).strip():
            domain.append(('name', 'ilike', str(search).strip()[:200]))
        conversations = Conversation.search(domain, limit=limit)
        return {'conversations': [conversation._serialize() for conversation in conversations]}

    @http.route('/nextbot/conversations/<int:conversation_id>', type='jsonrpc', auth='user')
    def update_conversation(
        self, conversation_id, name=None, archived=None, delete=False,
    ):
        conversation = self._conversation(conversation_id)
        if delete:
            conversation._delete_from_workspace()
            return {'deleted': True, 'id': conversation_id}
        values = {}
        if name is not None:
            clean_name = str(name).strip()[:120]
            if not clean_name:
                raise ValidationError(_('Conversation name cannot be empty.'))
            values['name'] = clean_name
        if archived is not None:
            values['active'] = not bool(archived)
        if values:
            conversation.sudo().write(values)
            if 'name' in values and conversation.channel_id.channel_type == 'group':
                conversation.channel_id.sudo().name = _('NextBot: %s', values['name'])
        return {'conversation': conversation._serialize()}

    @http.route('/nextbot/conversations/create', type='jsonrpc', auth='user')
    def create_conversation(self, name=None):
        conversation = request.env['nextbot.conversation']._create_for_user(name=name)
        return {'conversation': conversation._serialize()}

    @http.route('/nextbot/conversations/update', type='jsonrpc', auth='user')
    def update_conversation_alias(self, conversation_id, values=None):
        values = values if isinstance(values, dict) else {}
        archived = values.get('archived')
        if archived is None and 'active' in values:
            archived = not bool(values['active'])
        return self.update_conversation(
            conversation_id,
            name=values.get('name', values.get('title')),
            archived=archived,
        )

    @http.route('/nextbot/conversations/delete', type='jsonrpc', auth='user')
    def delete_conversation(self, conversation_id):
        return self.update_conversation(conversation_id, delete=True)

    @http.route(
        '/nextbot/conversations/<int:conversation_id>/messages',
        type='jsonrpc', auth='user', readonly=True,
    )
    def conversation_messages(self, conversation_id, before=None, limit=50):
        conversation = self._conversation(conversation_id)
        limit = min(max(int(limit or 50), 1), 100)
        domain = [
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', conversation.channel_id.id),
            ('message_type', '=', 'comment'),
        ]
        if before:
            domain.append(('id', '<', int(before)))
        messages_desc = request.env['mail.message'].search(domain, order='id desc', limit=limit + 1)
        has_more = len(messages_desc) > limit
        messages_desc = messages_desc[:limit]
        message_ids = messages_desc.ids
        runs = request.env['nextbot.run'].search([
            ('conversation_id', '=', conversation.id),
            '|',
            ('input_message_id', 'in', message_ids),
            ('response_message_id', 'in', message_ids),
        ]) if message_ids else request.env['nextbot.run']
        run_by_message = {}
        for run in runs:
            if run.response_message_id:
                run_by_message[run.response_message_id.id] = run
            elif run.input_message_id:
                # While a run is queued/running there is no assistant message
                # yet, so its user message carries the live event metadata.
                # Completed runs attach metadata only to the response to avoid
                # duplicate cards and inspector events after history reload.
                run_by_message[run.input_message_id.id] = run
        messages = list(reversed(messages_desc))
        serialized_messages = [self._serialize_message(message, run_by_message) for message in messages]
        return {
            'conversation_id': conversation.id,
            'messages': serialized_messages,
            'events': [
                event
                for serialized in serialized_messages
                for event in serialized.get('events', [])
            ],
            'has_more': has_more,
            'next_before': messages[0].id if has_more and messages else False,
            'next_cursor': messages[0].id if has_more and messages else False,
            'cursor': messages[0].id if has_more and messages else False,
        }

    @http.route('/nextbot/conversations/messages', type='jsonrpc', auth='user', readonly=True)
    def conversation_messages_alias(self, conversation_id, before=None, limit=50):
        return self.conversation_messages(conversation_id, before=before, limit=limit)

    @http.route('/nextbot/runs', type='jsonrpc', auth='user')
    def create_run(
        self, conversation_id=None, prompt=None, message=None, content=None,
        attachment_ids=None,
    ):
        conversation = (
            self._conversation(conversation_id)
            if conversation_id
            else request.env['nextbot.conversation']._create_for_user()
        )
        attachments = self._validate_run_attachments(conversation, attachment_ids or [])
        prompt = str(prompt if prompt is not None else message if message is not None else content or '').strip()
        if not prompt and attachments:
            prompt = _('Please review the attached file(s).')
        if not prompt:
            raise ValidationError(_('A NextBot run requires a message.'))
        prompt_limit = self._config_int('nextbot_agent.prompt_character_limit', 20000, 1000, 50000)
        if len(prompt) > prompt_limit:
            raise ValidationError(_('The message exceeds the %s character limit.', prompt_limit))
        active = request.env['nextbot.run'].search([
            ('conversation_id', '=', conversation.id),
            ('status', 'in', (
                'queued', 'planning', 'running', 'waiting_input',
                'waiting_approval', 'verifying',
            )),
        ], order='id desc', limit=1)
        if active:
            return active.action_steer(prompt, attachments=attachments)
        run = self._enqueue_run(conversation, prompt, attachments)
        return run._serialize(include_events=True)

    @http.route('/nextbot/runs/<int:run_id>', type='jsonrpc', auth='user', readonly=True)
    def run_snapshot(self, run_id):
        return self._run(run_id)._serialize(include_events=True)

    @http.route('/nextbot/runs/<int:run_id>/input', type='jsonrpc', auth='user')
    def steer_run(self, run_id, message=None, content=None, attachment_ids=None):
        run = self._run(run_id)
        attachments = self._validate_run_attachments(
            run.conversation_id, attachment_ids or [],
        )
        return run.action_steer(message if message is not None else content, attachments=attachments)

    @http.route('/nextbot/runs/<int:run_id>/continue', type='jsonrpc', auth='user')
    def continue_run(self, run_id):
        return self._run(run_id).action_continue()

    @http.route('/nextbot/runs/<int:run_id>/events', type='jsonrpc', auth='user', readonly=True)
    def run_events(self, run_id, after=0, limit=200):
        run = self._run(run_id)
        after = max(int(after or 0), 0)
        limit = min(max(int(limit or 200), 1), 500)
        events = request.env['nextbot.run.event'].search([
            ('run_id', '=', run.id),
            ('sequence', '>', after),
        ], order='sequence, id', limit=limit + 1)
        has_more = len(events) > limit
        events = events[:limit]
        return {
            'run_id': run.id,
            'status': run.status,
            'events': [event._serialize() for event in events],
            'next_after': events[-1].sequence if events else after,
            'last_sequence': events[-1].sequence if events else after,
            'cursor': events[-1].sequence if events else after,
            'has_more': has_more,
            'retry_after_ms': 650,
        }

    @http.route('/nextbot/runs/events', type='jsonrpc', auth='user', readonly=True)
    def run_events_alias(self, run_id, after=0, limit=200):
        return self.run_events(run_id, after=after, limit=limit)

    @http.route('/nextbot/runs/<int:run_id>/cancel', type='jsonrpc', auth='user')
    def cancel_run(self, run_id):
        return self._run(run_id).action_cancel()

    @http.route('/nextbot/runs/cancel', type='jsonrpc', auth='user')
    def cancel_run_alias(self, run_id):
        return self.cancel_run(run_id)

    @http.route('/nextbot/runs/<int:run_id>/regenerate', type='jsonrpc', auth='user')
    def regenerate_run(self, run_id):
        source = self._run(run_id)
        run = self._enqueue_run(
            source.conversation_id,
            source.prompt,
            source.attachment_ids,
            input_message=source.input_message_id,
        )
        return run._serialize(include_events=True)

    @http.route('/nextbot/runs/regenerate', type='jsonrpc', auth='user')
    def regenerate_run_alias(self, conversation_id, message_id):
        conversation = self._conversation(conversation_id)
        source = request.env['nextbot.run'].search([
            ('conversation_id', '=', conversation.id),
            '|',
            ('input_message_id', '=', int(message_id or 0)),
            ('response_message_id', '=', int(message_id or 0)),
        ], order='id desc', limit=1)
        if not source:
            raise UserError(_('The source NextBot run could not be found.'))
        run = self._enqueue_run(
            conversation,
            source.prompt,
            source.attachment_ids,
            input_message=source.input_message_id,
        )
        return run._serialize(include_events=True)

    @http.route('/nextbot/approvals/<int:approval_id>/approve', type='jsonrpc', auth='user')
    def approve(self, approval_id):
        return {'approval': self._approval(approval_id).action_approve()}

    @http.route('/nextbot/approvals/<int:approval_id>/reject', type='jsonrpc', auth='user')
    def reject(self, approval_id):
        return {'approval': self._approval(approval_id).action_reject()}

    @http.route('/nextbot/approvals/resolve', type='jsonrpc', auth='user')
    def resolve_approval(self, approval_id, decision):
        approval = self._approval(approval_id)
        if decision == 'approve':
            return {'approval': approval.action_approve()}
        if decision == 'reject':
            return {'approval': approval.action_reject()}
        raise ValidationError(_('Approval decision must be approve or reject.'))

    @http.route('/nextbot/tools', type='jsonrpc', auth='user', readonly=True)
    def tools(self):
        return {'tools': request.env['nextbot.tool.registry'].get_metadata()}

    @http.route('/nextbot/artifacts/<int:artifact_id>', type='jsonrpc', auth='user', readonly=True)
    def artifact(self, artifact_id):
        return {'artifact': self._artifact(artifact_id)._serialize(include_content=True)}

    @http.route('/nextbot/attachments', type='jsonrpc', auth='user')
    def upload_attachment(
        self, name, mimetype, data, size=None, conversation_id=None,
    ):
        conversation = (
            self._conversation(conversation_id)
            if conversation_id
            else request.env['nextbot.conversation']._create_for_user()
        )
        clean_name = os.path.basename(str(name or '').replace('\\', '/')).strip()[:255]
        if not clean_name or clean_name in ('.', '..'):
            raise ValidationError(_('Attachment name is invalid.'))
        clean_mimetype = str(mimetype or '').split(';', 1)[0].strip().lower()
        if clean_mimetype not in ALLOWED_ATTACHMENT_MIMETYPES:
            raise ValidationError(_('Attachment type %s is not allowed.', clean_mimetype or _('unknown')))
        encoded = str(data or '').strip()
        if encoded.startswith('data:'):
            header, separator, encoded = encoded.partition(',')
            if not separator or ';base64' not in header.lower():
                raise ValidationError(_('Attachment data URL must contain base64 data.'))
            declared_type = header[5:].split(';', 1)[0].lower()
            if declared_type and declared_type != clean_mimetype:
                raise ValidationError(_('Attachment MIME type does not match its data URL.'))
        max_bytes = self._config_int(
            'nextbot_agent.attachment_size_limit_mb', 20, 1, 50,
        ) * 1024 * 1024
        max_encoded_length = ((max_bytes + 2) // 3) * 4
        if len(encoded) > max_encoded_length:
            raise ValidationError(_('Attachment exceeds the configured size limit.'))
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValidationError(_('Attachment data is not valid base64.')) from error
        if size is not None:
            try:
                declared_size = int(size)
            except (TypeError, ValueError) as error:
                raise ValidationError(_('Attachment size is invalid.')) from error
            if declared_size != len(raw):
                raise ValidationError(_('Attachment size does not match the uploaded data.'))
        if not raw or len(raw) > max_bytes:
            raise ValidationError(_('Attachment must be non-empty and no larger than %s MB.', max_bytes // (1024 * 1024)))
        self._validate_magic(clean_mimetype, raw)
        attachment = request.env['ir.attachment'].create({
            'name': clean_name,
            'raw': raw,
            'mimetype': clean_mimetype,
            'res_model': 'discuss.channel',
            'res_id': conversation.channel_id.id,
        })
        return {
            'conversation_id': conversation.id,
            'attachment': {
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype,
                'size': attachment.file_size or len(raw),
                'url': '/web/content/%s?download=true' % attachment.id,
            },
        }

    @staticmethod
    def _validate_magic(mimetype, raw):
        valid = True
        if mimetype == 'application/pdf':
            valid = raw.startswith(b'%PDF-')
        elif mimetype == 'image/png':
            valid = raw.startswith(b'\x89PNG\r\n\x1a\n')
        elif mimetype == 'image/jpeg':
            valid = raw.startswith(b'\xff\xd8\xff')
        elif mimetype == 'image/gif':
            valid = raw.startswith((b'GIF87a', b'GIF89a'))
        elif mimetype == 'image/webp':
            valid = len(raw) >= 12 and raw.startswith(b'RIFF') and raw[8:12] == b'WEBP'
        elif mimetype.startswith('text/'):
            valid = b'\x00' not in raw[:4096]
        if not valid:
            raise ValidationError(_('Attachment contents do not match the declared MIME type.'))
