# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import base64
import datetime
import decimal
import json
import re
from urllib.parse import parse_qs, unquote, urlparse

from markupsafe import Markup

from nwos import api, models, _
from nwos.exceptions import AccessError, MissingError, UserError, ValidationError
from nwos.service.model import get_public_method
from nwos.tools import hash_sign, verify_hash_signed


_BLOCKED_MODELS = {
    'auth.passkey.key',
    'certificate.key',
    'ir.config_parameter',
    'ir.logging',
    'ir.profile',
    'res.users.apikeys',
    'res.users.apikeys.description',
    'res.users.apikeys.show',
    'res.users.identitycheck',
}

_BLOCKED_FIELDS = {
    'password', 'new_password', 'password_crypt', 'api_key',
    'secret', 'client_secret', 'access_token', 'refresh_token',
    'oauth_access_token', 'signup_token', 'totp_secret', 'private_key',
    'credential', 'session_identifier', 'smtp_pass',
    'provider_ref',
    'db_datas', 'store_fname', 'checksum',
    'index_content',
}
_SENSITIVE_FIELD_RE = re.compile(
    r'(?:^|_)(?:password|passwd|pass|secret|api_?key|access_?token|refresh_?token|'
    r'private_?key|credential|signup_?token|totp)(?:$|_)|(?:^|_)token$',
    re.IGNORECASE,
)
_SAFE_CONTEXT_KEYS = {'active_test', 'lang', 'tz', 'allowed_company_ids'}
_FORBIDDEN_WORKFLOW_METHODS = {
    'browse', 'check_access', 'check_access_rights', 'check_access_rule',
    'copy', 'copy_data', 'create', 'default_get', 'ensure_one', 'exists',
    'export_data', 'fetch', 'fields_get', 'filtered', 'filtered_domain',
    'flush_model', 'flush_recordset', 'get_metadata', 'has_access',
    'invalidate_model', 'invalidate_recordset', 'load', 'mapped', 'name_create',
    'read', 'read_group', 'search', 'search_count', 'search_fetch', 'search_read',
    'sorted', 'sudo', 'toggle_active', 'action_archive', 'action_unarchive',
    'unlink', 'update', 'web_read', 'web_save', 'with_company', 'with_context',
    'with_env', 'with_prefetch', 'with_user', 'write',
}


def _object_schema(properties=None, required=None, additional=False):
    return {
        'type': 'object',
        'properties': properties or {},
        'required': required or [],
        'additionalProperties': additional,
    }


def _array(items, **kwargs):
    return {'type': 'array', 'items': items, **kwargs}


_MODEL = {'type': 'string', 'description': 'Registered ORM model name, for example res.partner.'}
_IDS = _array({'type': 'integer', 'minimum': 1}, minItems=1, uniqueItems=True)
_DOMAIN = _array({}, description='ORM domain expressed as JSON arrays.')
_CONTEXT = _object_schema({
    'active_test': {'type': 'boolean'},
    'lang': {'type': 'string'},
    'tz': {'type': 'string'},
    'allowed_company_ids': _array({'type': 'integer'}),
})


def _tool(name, description, schema, *, read_only=True, destructive=False, idempotent=True):
    return {
        'name': name,
        'description': description,
        'inputSchema': schema,
        'outputSchema': _object_schema(additional=True),
        'annotations': {
            'readOnlyHint': read_only,
            'destructiveHint': destructive,
            'idempotentHint': idempotent,
            'openWorldHint': False,
        },
    }


_TOOLS = [
    _tool('models_list', 'List installed ORM models available to the authenticated user.', _object_schema({
        'query': {'type': 'string'}, 'limit': {'type': 'integer', 'minimum': 1},
        'cursor': {'type': 'string'},
    })),
    _tool(
        'model_schema',
        'Describe safe fields, relations, selection values and enabled MCP operations.',
        _object_schema({'model': _MODEL}, ['model']),
    ),
    _tool('model_views', 'Return the effective view architecture for an accessible model.', _object_schema({
        'model': _MODEL,
        'types': _array({'type': 'string', 'description': 'Installed non-QWeb view type.'}),
    }, ['model'])),
    _tool('records_search_read', 'Search and read records through normal ACLs and record rules.', _object_schema({
        'model': _MODEL, 'domain': _DOMAIN, 'fields': _array({'type': 'string'}),
        'order': {'type': 'string'}, 'limit': {'type': 'integer', 'minimum': 1},
        'cursor': {'type': 'string'}, 'context': _CONTEXT,
    }, ['model'])),
    _tool('records_read', 'Read selected records through normal ACLs and record rules.', _object_schema({
        'model': _MODEL, 'ids': _IDS, 'fields': _array({'type': 'string'}), 'context': _CONTEXT,
    }, ['model', 'ids'])),
    _tool('records_group', 'Aggregate records using ORM grouping and record rules.', _object_schema({
        'model': _MODEL, 'domain': _DOMAIN, 'groupby': _array({'type': 'string'}, minItems=1),
        'aggregates': _array({'type': 'string'}), 'order': {'type': 'string'},
        'limit': {'type': 'integer', 'minimum': 1}, 'cursor': {'type': 'string'},
        'context': _CONTEXT,
    }, ['model', 'groupby'])),
    _tool('record_create', 'Create one record when MCP creation is enabled for the model.', _object_schema({
        'model': _MODEL, 'values': _object_schema(additional=True), 'context': _CONTEXT,
    }, ['model', 'values']), read_only=False, idempotent=False),
    _tool('records_update', 'Update selected records when MCP updates are enabled for the model.', _object_schema({
        'model': _MODEL, 'ids': _IDS, 'values': _object_schema(additional=True), 'context': _CONTEXT,
    }, ['model', 'ids', 'values']), read_only=False),
    _tool('records_delete_preview', 'Preview a deletion and issue a short-lived confirmation token.', _object_schema({
        'model': _MODEL, 'ids': _IDS, 'context': _CONTEXT,
    }, ['model', 'ids'])),
    _tool(
        'records_delete_confirm',
        'Delete exactly the previewed records with a one-time confirmation token.',
        _object_schema({
            'model': _MODEL, 'ids': _IDS,
            'confirmation_token': {'type': 'string'}, 'context': _CONTEXT,
        }, ['model', 'ids', 'confirmation_token']),
        read_only=False,
        destructive=True,
    ),
    _tool('action_preview', 'Preview an administrator-allowlisted public workflow method.', _object_schema({
        'model': _MODEL, 'ids': _IDS, 'method': {'type': 'string'},
        'args': _array({}), 'kwargs': _object_schema(additional=True), 'context': _CONTEXT,
    }, ['model', 'ids', 'method'])),
    _tool(
        'action_confirm',
        'Run the exact previewed workflow method with a one-time confirmation token.',
        _object_schema({
            'model': _MODEL, 'ids': _IDS, 'method': {'type': 'string'},
            'args': _array({}), 'kwargs': _object_schema(additional=True),
            'confirmation_token': {'type': 'string'}, 'context': _CONTEXT,
        }, ['model', 'ids', 'method', 'confirmation_token']),
        read_only=False,
        destructive=True,
        idempotent=False,
    ),
    _tool('reports_list', 'List reports enabled for an accessible model.', _object_schema({
        'model': _MODEL, 'context': _CONTEXT,
    }, ['model'])),
    _tool('report_render', 'Render a permitted report and return a short-lived binary resource URI.', _object_schema({
        'model': _MODEL, 'ids': _IDS, 'report_id': {'type': 'integer', 'minimum': 1},
        'format': {'type': 'string', 'enum': ['pdf', 'html', 'text']}, 'context': _CONTEXT,
    }, ['model', 'ids', 'report_id'])),
    _tool('attachments_list', 'List attachments on permitted records without embedding their content.', _object_schema({
        'model': _MODEL, 'ids': _IDS, 'limit': {'type': 'integer', 'minimum': 1},
        'context': _CONTEXT,
    }, ['model', 'ids'])),
    _tool(
        'binary_field_download',
        'Create a short-lived download resource for an accessible binary or image field.',
        _object_schema({
            'model': _MODEL, 'id': {'type': 'integer', 'minimum': 1},
            'field': {'type': 'string'}, 'filename': {'type': 'string'},
            'mimetype': {'type': 'string'}, 'context': _CONTEXT,
        }, ['model', 'id', 'field']),
    ),
    _tool('attachment_upload', 'Upload an attachment when attachment access is enabled.', _object_schema({
        'model': _MODEL, 'id': {'type': 'integer', 'minimum': 1}, 'name': {'type': 'string'},
        'mimetype': {'type': 'string'}, 'data': {'type': 'string', 'description': 'Base64-encoded content.'},
        'context': _CONTEXT,
    }, ['model', 'id', 'name', 'data']), read_only=False, idempotent=False),
]


_PROMPTS = [
    ('record_lookup', 'Find records safely with model discovery and bounded search.'),
    ('record_summary', 'Read and summarize selected records without exposing binary or secret fields.'),
    ('record_create', 'Plan and create one policy-permitted business record.'),
    ('update_planning', 'Inspect records and plan a bounded, policy-permitted update.'),
    ('workflow_execution', 'Preview and confirm an allowlisted workflow action.'),
    ('cross_model_analysis', 'Discover related models and analyze records with bounded searches and groups.'),
]


class McpGateway(models.AbstractModel):
    _name = 'mcp.gateway'
    _description = 'MCP Gateway Service'

    # ------------------------------------------------------------------
    # Public controller contract
    # ------------------------------------------------------------------

    @api.model
    @api.private
    def tools_list(self, cursor=None):
        offset = self._cursor_offset(cursor, 'tools') if cursor else 0
        page_size = self._global_page_size()
        values = _TOOLS[offset:offset + page_size]
        result = {'tools': values}
        if offset + page_size < len(_TOOLS):
            result['nextCursor'] = self._make_cursor('tools', offset + page_size)
        return result

    @api.model
    @api.private
    def tools_call(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ValidationError(_('Tool arguments must be an object.'))
        handlers = {
            'models_list': self._tool_models_list,
            'model_schema': self._tool_model_schema,
            'model_views': self._tool_model_views,
            'records_search_read': self._tool_records_search_read,
            'records_read': self._tool_records_read,
            'records_group': self._tool_records_group,
            'record_create': self._tool_record_create,
            'records_update': self._tool_records_update,
            'records_delete_preview': self._tool_records_delete_preview,
            'records_delete_confirm': self._tool_records_delete_confirm,
            'action_preview': self._tool_action_preview,
            'action_confirm': self._tool_action_confirm,
            'reports_list': self._tool_reports_list,
            'report_render': self._tool_report_render,
            'attachments_list': self._tool_attachments_list,
            'binary_field_download': self._tool_binary_field_download,
            'attachment_upload': self._tool_attachment_upload,
        }
        handler = handlers.get(name)
        if not handler:
            raise ValidationError(_('Unknown MCP tool: %s', name))
        data = self._json_safe(handler(arguments))
        return self._tool_result(data)

    @api.model
    @api.private
    def download(self, token):
        """Consume an expiring download token for the HTTP download route."""
        value = self.env['mcp.download.token'].consume(token)
        try:
            content = base64.b64decode(value.get('blob') or '', validate=True)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('The download payload is invalid.')) from error
        return {
            'filename': value.get('name') or 'download',
            'mimetype': value.get('mimeType') or 'application/octet-stream',
            'content': content,
        }

    @api.model
    @api.private
    def resources_list(self, cursor=None):
        offset = self._cursor_offset(cursor, 'resources') if cursor else 0
        models_data = self._accessible_models()
        page_size = self._global_page_size()
        page = models_data[offset:offset + page_size]
        result = {
            'resources': [{
                'uri': 'nextosp://model/%s/schema' % item['model'],
                'name': '%s schema' % item['name'],
                'description': 'Safe ORM schema and MCP policy for %s.' % item['model'],
                'mimeType': 'application/json',
            } for item in page],
        }
        if offset + page_size < len(models_data):
            result['nextCursor'] = self._make_cursor('resources', offset + page_size)
        return result

    @api.model
    @api.private
    def resource_templates_list(self, cursor=None):
        templates = [
            {
                'uriTemplate': 'nextosp://model/{model}/schema',
                'name': 'Model schema', 'mimeType': 'application/json',
                'description': 'Schema and MCP policy for an accessible model.',
            },
            {
                'uriTemplate': 'nextosp://record/{model}/{id}',
                'name': 'Record', 'mimeType': 'application/json',
                'description': 'A safe default projection of one accessible record.',
            },
            {
                'uriTemplate': 'nextosp://search/{model}?domain={domain}&fields={fields}&limit={limit}',
                'name': 'Record search', 'mimeType': 'application/json',
                'description': 'A bounded ORM search; domain and fields are URL-encoded JSON.',
            },
            {
                'uriTemplate': 'nextosp://attachment/{id}',
                'name': 'Attachment download', 'mimeType': 'application/json',
                'description': 'An authenticated download descriptor for an accessible attachment.',
            },
            {
                'uriTemplate': 'nextosp://report/{model}/{report_id}/{ids}?format={format}',
                'name': 'Generated report', 'mimeType': 'application/json',
                'description': 'Render a permitted report and return an authenticated download descriptor.',
            },
            {
                'uriTemplate': 'nextosp://binary/{token}',
                'name': 'Expiring binary download', 'mimeType': 'application/json',
                'description': (
                    'A descriptor for a short-lived, user-bound, single-use '
                    'authenticated download.'
                ),
            },
        ]
        offset = self._cursor_offset(cursor, 'resource_templates') if cursor else 0
        page_size = self._global_page_size()
        result = {'resourceTemplates': templates[offset:offset + page_size]}
        if offset + page_size < len(templates):
            result['nextCursor'] = self._make_cursor(
                'resource_templates',
                offset + page_size,
            )
        return result

    @api.model
    @api.private
    def resources_read(self, uri):
        if not isinstance(uri, str) or not uri.startswith('nextosp://'):
            raise ValidationError(_('Unsupported MCP resource URI.'))
        parsed = urlparse(uri)
        kind = parsed.netloc
        parts = [unquote(part) for part in parsed.path.split('/') if part]
        if kind == 'model' and len(parts) == 2 and parts[1] == 'schema':
            data = self._tool_model_schema({'model': parts[0]})
            return self._resource_result(uri, data)
        if kind == 'record' and len(parts) == 2:
            try:
                record_id = int(parts[1])
            except ValueError as error:
                raise ValidationError(_('Invalid record resource URI.')) from error
            data = self._tool_records_read({'model': parts[0], 'ids': [record_id]})
            return self._resource_result(uri, data)
        if kind == 'search' and len(parts) == 1:
            query = parse_qs(parsed.query, keep_blank_values=False)
            arguments = {'model': parts[0]}
            for key in ('domain', 'fields'):
                if key in query:
                    try:
                        arguments[key] = json.loads(query[key][0])
                    except (TypeError, ValueError) as error:
                        raise ValidationError(_('Invalid JSON in resource query.')) from error
            if 'limit' in query:
                try:
                    arguments['limit'] = int(query['limit'][0])
                except ValueError as error:
                    raise ValidationError(_('Invalid resource result limit.')) from error
            data = self._tool_records_search_read(arguments)
            return self._resource_result(uri, data)
        if kind == 'attachment' and len(parts) == 1:
            try:
                attachment_id = int(parts[0])
            except ValueError as error:
                raise ValidationError(_('Invalid attachment resource URI.')) from error
            attachment = self.env['ir.attachment'].browse(attachment_id).exists()
            if not attachment:
                raise MissingError(_('The requested attachment does not exist.'))
            attachment.check_access('read')
            if not attachment.res_model or not attachment.res_id:
                raise AccessError(_('The attachment is not linked to an exposed record.'))
            model, _policy = self._get_model(attachment.res_model, 'attachments')
            source = model.browse(attachment.res_id).exists()
            self._ensure_complete(source, [attachment.res_id])
            source.check_access('read')
            attachment = model.env['ir.attachment'].browse(attachment.id)
            resource = model.env['mcp.download.token'].issue(
                attachment.name,
                mimetype=attachment.mimetype,
                attachment=attachment,
                model_name=model._name,
                res_id=attachment.res_id,
            )
            return self._resource_result(uri, {'resource': resource})
        if kind == 'report' and len(parts) == 3:
            try:
                report_id = int(parts[1])
                record_ids = [int(value) for value in parts[2].split(',') if value]
            except ValueError as error:
                raise ValidationError(_('Invalid report resource URI.')) from error
            query = parse_qs(parsed.query, keep_blank_values=False)
            arguments = {
                'model': parts[0],
                'report_id': report_id,
                'ids': record_ids,
            }
            if 'format' in query:
                arguments['format'] = query['format'][0]
            data = self._tool_report_render(arguments)
            return self._resource_result(uri, data)
        if kind == 'binary' and len(parts) == 1:
            return self._resource_result(uri, {
                'downloadUrl': '/mcp/download/%s' % parts[0],
                'authentication': 'Bearer API key',
                'singleUse': True,
            })
        raise ValidationError(_('Unknown MCP resource URI.'))

    @api.model
    @api.private
    def prompts_list(self, cursor=None):
        offset = self._cursor_offset(cursor, 'prompts') if cursor else 0
        page_size = self._global_page_size()
        page = _PROMPTS[offset:offset + page_size]
        result = {'prompts': [{
            'name': name,
            'description': description,
            'arguments': [
                {'name': 'model', 'description': 'ORM model name', 'required': name != 'cross_model_analysis'},
                {'name': 'goal', 'description': 'Desired business outcome', 'required': True},
            ],
        } for name, description in page]}
        if offset + page_size < len(_PROMPTS):
            result['nextCursor'] = self._make_cursor('prompts', offset + page_size)
        return result

    @api.model
    @api.private
    def prompts_get(self, name, arguments):
        arguments = arguments or {}
        known = dict(_PROMPTS)
        if name not in known:
            raise ValidationError(_('Unknown MCP prompt: %s', name))
        goal = str(arguments.get('goal') or '').strip()
        if not goal:
            raise ValidationError(_('The goal prompt argument is required.'))
        model_name = str(arguments.get('model') or '').strip()
        if model_name:
            self._get_model(model_name, 'read')
        guidance = {
            'record_lookup': (
                'Discover the model schema, then use records_search_read with '
                'explicit fields and a bounded limit.'
            ),
            'record_summary': (
                'Read only the necessary safe fields. Treat relations as identifiers '
                'and never request secrets or binary content.'
            ),
            'record_create': (
                'Inspect model_schema first, ask for missing required business '
                'values, then call record_create only once.'
            ),
            'update_planning': (
                'Read current values first, describe the intended changes, then call '
                'records_update with the smallest record set.'
            ),
            'workflow_execution': (
                'Inspect records first. Use action_preview, present the preview, and '
                'call action_confirm only with its exact token and arguments.'
            ),
            'cross_model_analysis': (
                'Discover relevant models and relations, then prefer records_group '
                'and bounded searches over bulk reads.'
            ),
        }[name]
        text = '%s\n\nGoal: %s' % (guidance, goal)
        if model_name:
            text += '\nModel: %s' % model_name
        return {
            'description': known[name],
            'messages': [{'role': 'user', 'content': {'type': 'text', 'text': text}}],
        }

    # ------------------------------------------------------------------
    # Generic tool implementations
    # ------------------------------------------------------------------

    def _tool_models_list(self, arguments):
        query = str(arguments.get('query') or '').strip().lower()
        all_models = self._accessible_models()
        if query:
            all_models = [
                item for item in all_models
                if query in item['model'].lower() or query in item['name'].lower()
            ]
        fingerprint = self._digest({'query': query})
        offset = self._bound_cursor(arguments.get('cursor'), 'models_list', fingerprint)
        limit = self._page_limit(arguments.get('limit'))
        page = all_models[offset:offset + limit + 1]
        result = {'models': page[:limit]}
        if len(page) > limit:
            result['nextCursor'] = self._make_cursor('models_list', offset + limit, fingerprint)
        return result

    def _tool_model_schema(self, arguments):
        model, policy = self._get_model(arguments.get('model'), 'discover')
        field_names = self._safe_fields(model, all_fields=True)
        descriptions = model.fields_get(
            allfields=field_names,
            attributes=['string', 'type', 'help', 'required', 'readonly', 'relation', 'selection', 'store'],
        )
        model_record = self.env['ir.model']._get(model._name)
        operations = {
            'discover': policy['allow_discovery'],
            'read': policy['allow_read'] and model.browse().has_access('read'),
            'create': policy['allow_create'] and model.browse().has_access('create'),
            'update': policy['allow_update'] and model.browse().has_access('write'),
            'delete': policy['allow_delete'] and model.browse().has_access('unlink'),
            'reports': policy['allow_reports'],
            'attachments': policy['allow_attachments'],
        }
        return {
            'model': model._name,
            'name': str(model._description),
            'modules': model_record.modules or '',
            'fields': descriptions,
            'operations': operations,
            'workflow_methods': sorted(policy['workflow_methods']),
            'max_results': min(policy['max_results'], self._global_page_size()),
            'configured_policy': policy['configured'],
        }

    def _tool_model_views(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'read')
        requested = arguments.get('types') or ['form', 'list', 'search']
        if not isinstance(requested, list) or not requested:
            raise ValidationError(_('View types must be a non-empty array.'))
        allowed_view_types = self._allowed_view_types()
        invalid = set(requested) - allowed_view_types
        if invalid:
            raise ValidationError(_('Unsupported view type: %s', ', '.join(sorted(invalid))))
        views = {}
        for view_type in requested:
            try:
                value = model.get_view(view_type=view_type)
            except (UserError, ValueError):
                continue
            views[view_type] = {
                key: value[key]
                for key in ('id', 'type', 'model', 'arch')
                if key in value
            }
        return {'model': model._name, 'views': views}

    def _tool_records_search_read(self, arguments):
        model, policy = self._get_model(arguments.get('model'), 'read')
        model = self._with_safe_context(model, arguments.get('context'))
        domain = arguments.get('domain') or []
        if not isinstance(domain, list):
            raise ValidationError(_('Domain must be an array.'))
        field_names = self._safe_fields(model, arguments.get('fields'))
        order = arguments.get('order') or None
        self._validate_domain(model, domain)
        self._validate_order(model, order)
        fingerprint = self._digest({
            'model': model._name, 'domain': domain, 'fields': field_names,
            'order': order, 'context': arguments.get('context') or {},
        })
        offset = self._bound_cursor(arguments.get('cursor'), 'records_search_read', fingerprint)
        limit = self._page_limit(arguments.get('limit'), policy)
        rows = model.search_read(domain, field_names, offset=offset, limit=limit + 1, order=order)
        result = {'records': rows[:limit]}
        if len(rows) > limit:
            result['nextCursor'] = self._make_cursor('records_search_read', offset + limit, fingerprint)
        return result

    def _tool_records_read(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'read')
        model = self._with_safe_context(model, arguments.get('context'))
        record_ids = self._record_ids(arguments.get('ids'))
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('read')
        field_names = self._safe_fields(model, arguments.get('fields'))
        return {'records': records.read(field_names)}

    def _tool_records_group(self, arguments):
        model, policy = self._get_model(arguments.get('model'), 'read')
        model = self._with_safe_context(model, arguments.get('context'))
        domain = arguments.get('domain') or []
        groupby = arguments.get('groupby') or []
        aggregates = arguments.get('aggregates') or ['__count']
        if not isinstance(domain, list) or not isinstance(groupby, list) or not groupby:
            raise ValidationError(_('A domain array and at least one group-by field are required.'))
        self._validate_group_specs(model, groupby, aggregates)
        order = arguments.get('order') or None
        self._validate_domain(model, domain)
        self._validate_order(model, order, allowed_specs=set(groupby) | set(aggregates))
        fingerprint = self._digest({
            'model': model._name, 'domain': domain, 'groupby': groupby,
            'aggregates': aggregates, 'order': order, 'context': arguments.get('context') or {},
        })
        offset = self._bound_cursor(arguments.get('cursor'), 'records_group', fingerprint)
        limit = self._page_limit(arguments.get('limit'), policy)
        if hasattr(model, 'formatted_read_group'):
            rows = model.formatted_read_group(
                domain, groupby=groupby, aggregates=aggregates,
                offset=offset, limit=limit + 1, order=order,
            )
        else:
            legacy_fields = list(dict.fromkeys(groupby + aggregates))
            rows = model.read_group(
                domain, legacy_fields, groupby, offset=offset, limit=limit + 1,
                orderby=order or False, lazy=False,
            )
        result = {'groups': rows[:limit]}
        if len(rows) > limit:
            result['nextCursor'] = self._make_cursor('records_group', offset + limit, fingerprint)
        return result

    def _tool_record_create(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'create')
        model = self._with_safe_context(model, arguments.get('context'))
        values = self._safe_values(model, arguments.get('values'))
        record = model.create(values)
        record.check_access('read')
        return {'record': record.read(self._safe_fields(model, ['id', 'display_name']))[0]}

    def _tool_records_update(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'update')
        model = self._with_safe_context(model, arguments.get('context'))
        record_ids = self._record_ids(arguments.get('ids'))
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('write')
        values = self._safe_values(model, arguments.get('values'), records=records)
        records.write(values)
        return {'updated_ids': records.ids, 'count': len(records)}

    def _tool_records_delete_preview(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'delete')
        model = self._with_safe_context(model, arguments.get('context'))
        record_ids = self._record_ids(arguments.get('ids'))
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('unlink')
        preview = {
            'operation': 'delete', 'model': model._name,
            'records': records.read(self._safe_fields(model, ['id', 'display_name'])),
            'count': len(records),
        }
        token_arguments = {'context': self._normalize_context(arguments.get('context'))}
        preview.update(model.env['mcp.confirmation.token'].issue(
            'delete', model._name, records.ids, arguments=token_arguments, preview=preview,
        ))
        return preview

    def _tool_records_delete_confirm(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'delete')
        model = self._with_safe_context(model, arguments.get('context'))
        record_ids = self._record_ids(arguments.get('ids'))
        token_arguments = {'context': self._normalize_context(arguments.get('context'))}
        model.env['mcp.confirmation.token'].consume(
            arguments.get('confirmation_token'), 'delete', model._name, record_ids,
            arguments=token_arguments,
        )
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('unlink')
        records.unlink()
        return {'deleted_ids': record_ids, 'count': len(record_ids)}

    def _tool_action_preview(self, arguments):
        model, policy = self._get_model(arguments.get('model'), 'read')
        model = self._with_safe_context(model, arguments.get('context'))
        method_name, args, kwargs = self._action_arguments(model, policy, arguments)
        record_ids = self._record_ids(arguments.get('ids'))
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('write')
        token_arguments = {
            'args': args, 'kwargs': kwargs,
            'context': self._normalize_context(arguments.get('context')),
        }
        preview = {
            'operation': 'action', 'model': model._name, 'method': method_name,
            'records': records.read(self._safe_fields(model, ['id', 'display_name'])),
            'arguments': token_arguments,
        }
        preview.update(model.env['mcp.confirmation.token'].issue(
            'action', model._name, records.ids, method_name=method_name,
            arguments=token_arguments, preview=preview,
        ))
        return preview

    def _tool_action_confirm(self, arguments):
        model, policy = self._get_model(arguments.get('model'), 'read')
        model = self._with_safe_context(model, arguments.get('context'))
        method_name, args, kwargs = self._action_arguments(model, policy, arguments)
        record_ids = self._record_ids(arguments.get('ids'))
        token_arguments = {
            'args': args, 'kwargs': kwargs,
            'context': self._normalize_context(arguments.get('context')),
        }
        model.env['mcp.confirmation.token'].consume(
            arguments.get('confirmation_token'), 'action', model._name, record_ids,
            method_name=method_name, arguments=token_arguments,
        )
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('write')
        method = get_public_method(records, method_name)
        result = method(records, *args, **kwargs)
        return {'model': model._name, 'ids': record_ids, 'method': method_name, 'result': result}

    def _tool_reports_list(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'reports')
        model = self._with_safe_context(model, arguments.get('context'))
        reports = model.env['ir.actions.report'].search(
            [('model', '=', model._name)],
            limit=self._global_page_size(),
        )
        reports = reports.filtered(self._report_allowed)
        return {'reports': [{
            'id': report.id, 'name': report.name, 'report_name': report.report_name,
            'report_type': report.report_type, 'multi': report.multi,
        } for report in reports]}

    def _tool_report_render(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'reports')
        model = self._with_safe_context(model, arguments.get('context'))
        record_ids = self._record_ids(arguments.get('ids'))
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('read')
        report_id = arguments.get('report_id')
        if isinstance(report_id, bool) or not isinstance(report_id, int) or report_id <= 0:
            raise ValidationError(_('Report ID must be a positive integer.'))
        Report = model.env['ir.actions.report']
        report = Report.browse(report_id).exists()
        if not report or report.model != model._name or not self._report_allowed(report):
            raise AccessError(_('The requested report is not available for this model.'))
        output_format = arguments.get('format') or ('pdf' if report.report_type == 'qweb-pdf' else 'html')
        if output_format == 'pdf':
            content, actual_format = Report._render_qweb_pdf(report.id, records.ids)
            mimetype = 'application/pdf'
        elif output_format == 'html':
            content, actual_format = Report._render_qweb_html(report.id, records.ids)
            mimetype = 'text/html'
        elif output_format == 'text':
            content, actual_format = Report._render_qweb_text(report.id, records.ids)
            mimetype = 'text/plain'
        else:
            raise ValidationError(_('Unsupported report format.'))
        extension = actual_format or output_format
        filename = '%s.%s' % (re.sub(r'[^A-Za-z0-9._-]+', '_', report.name), extension)
        resource = model.env['mcp.download.token'].issue(
            filename, mimetype=mimetype, payload=base64.b64encode(content),
            report=report, model_name=model._name, record_ids=records.ids,
        )
        return {'resource': resource, 'record_ids': records.ids, 'report_id': report.id}

    def _tool_attachments_list(self, arguments):
        model, policy = self._get_model(arguments.get('model'), 'attachments')
        model = self._with_safe_context(model, arguments.get('context'))
        record_ids = self._record_ids(arguments.get('ids'))
        records = model.browse(record_ids).exists()
        self._ensure_complete(records, record_ids)
        records.check_access('read')
        limit = self._page_limit(arguments.get('limit'), policy)
        attachments = model.env['ir.attachment'].search([
            ('res_model', '=', model._name), ('res_id', 'in', record_ids),
        ], limit=limit)
        values = []
        for attachment in attachments:
            resource = model.env['mcp.download.token'].issue(
                attachment.name, mimetype=attachment.mimetype, attachment=attachment,
                model_name=model._name, res_id=attachment.res_id,
            )
            values.append({
                'id': attachment.id, 'name': attachment.name,
                'mimetype': attachment.mimetype, 'file_size': attachment.file_size,
                'res_id': attachment.res_id, 'resource': resource,
            })
        return {'attachments': values}

    def _tool_binary_field_download(self, arguments):
        model, policy = self._get_model(arguments.get('model'), 'attachments')
        model = self._with_safe_context(model, arguments.get('context'))
        record_id = self._record_ids([arguments.get('id')])[0]
        record = model.browse(record_id).exists()
        self._ensure_complete(record, [record_id])
        record.check_access('read')
        field_name = arguments.get('field')
        field = model._fields.get(field_name) if isinstance(field_name, str) else None
        if (
            not field or field.type != 'binary'
            or self._field_name_is_sensitive(field_name)
            or not record._has_field_access(field, 'read')
            or field_name in policy['blocked_fields']
            or (
                policy['allowed_fields']
                and field_name not in policy['allowed_fields']
            )
        ):
            raise AccessError(_('The binary field is not accessible through MCP.'))
        default_name = '%s-%s' % (record.display_name, field_name)
        filename = str(arguments.get('filename') or default_name).replace('\\', '/').rsplit('/', 1)[-1]
        filename = filename.replace('\x00', '')[:255] or field_name
        mimetype = str(arguments.get('mimetype') or 'application/octet-stream')
        if '\r' in mimetype or '\n' in mimetype or len(mimetype) > 255:
            raise ValidationError(_('Invalid binary MIME type.'))
        resource = model.env['mcp.download.token'].issue(
            filename, mimetype=mimetype, model_name=model._name,
            res_id=record.id, field_name=field_name,
        )
        return {
            'model': model._name, 'id': record.id, 'field': field_name,
            'resource': resource,
        }

    def _tool_attachment_upload(self, arguments):
        model, _policy = self._get_model(arguments.get('model'), 'attachments')
        model = self._with_safe_context(model, arguments.get('context'))
        record_id = self._record_ids([arguments.get('id')])[0]
        record = model.browse(record_id).exists()
        self._ensure_complete(record, [record_id])
        record.check_access('write')
        name = str(arguments.get('name') or '').strip()
        if not name or len(name) > 255:
            raise ValidationError(_('An attachment name of at most 255 characters is required.'))
        encoded = arguments.get('data') or ''
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as error:
            raise ValidationError(_('Attachment data must be valid base64.')) from error
        max_size = self._integer_param('mcp.max_request_bytes', 1_048_576, minimum=1024, maximum=100_000_000)
        if len(decoded) > max_size:
            raise ValidationError(_('The attachment exceeds the configured MCP request limit.'))
        attachment = model.env['ir.attachment'].create({
            'name': name, 'mimetype': arguments.get('mimetype') or 'application/octet-stream',
            'datas': base64.b64encode(decoded), 'res_model': model._name, 'res_id': record.id,
        })
        resource = model.env['mcp.download.token'].issue(
            attachment.name, mimetype=attachment.mimetype, attachment=attachment,
            model_name=model._name, res_id=record.id,
        )
        return {'attachment': {
            'id': attachment.id, 'name': attachment.name,
            'mimetype': attachment.mimetype, 'file_size': attachment.file_size,
            'resource': resource,
        }}

    # ------------------------------------------------------------------
    # Security, pagination and serialization helpers
    # ------------------------------------------------------------------

    def _accessible_models(self):
        result = []
        Policy = self.env['mcp.policy']
        policy_map = Policy._effective_policy_map()
        default_policy = Policy._default_effective_policy()
        for model_name in sorted(self.env):
            try:
                model, policy = self._get_model(
                    model_name,
                    'discover',
                    policy=policy_map.get(model_name, default_policy),
                )
            except (AccessError, ValidationError):
                continue
            result.append({
                'model': model_name,
                'name': str(model._description),
                'operations': {
                    'read': policy['allow_read'] and model.browse().has_access('read'),
                    'create': policy['allow_create'] and model.browse().has_access('create'),
                    'update': policy['allow_update'] and model.browse().has_access('write'),
                    'delete': policy['allow_delete'] and model.browse().has_access('unlink'),
                },
            })
        return result

    def _get_model(self, model_name, operation, *, policy=None):
        if not isinstance(model_name, str) or not model_name or model_name not in self.env:
            raise ValidationError(_('Unknown model: %s', model_name or ''))
        model = self.env[model_name]
        if (
            model_name in _BLOCKED_MODELS or model_name.startswith('mcp.')
            or model._abstract or model._transient
        ):
            raise AccessError(_('The model is not exposed through MCP.'))
        policy = policy or self.env['mcp.policy']._effective_for_model(model_name)
        policy_key = {
            'discover': 'allow_discovery', 'read': 'allow_read',
            'create': 'allow_create', 'update': 'allow_update',
            'delete': 'allow_delete', 'reports': 'allow_reports',
            'attachments': 'allow_attachments',
        }.get(operation)
        if not policy_key or not policy[policy_key]:
            raise AccessError(_('The MCP policy does not allow this operation.'))
        access_operation = {
            'discover': 'read', 'read': 'read', 'create': 'create',
            'update': 'write', 'delete': 'unlink', 'reports': 'read',
            'attachments': 'read',
        }[operation]
        if not model.browse().has_access(access_operation):
            raise AccessError(_('The authenticated user cannot access this model.'))
        return model, policy

    def _safe_fields(self, model, requested=None, *, write=False, all_fields=False):
        policy = self.env['mcp.policy']._effective_for_model(model._name)
        descriptions = model.fields_get(attributes=['type', 'readonly'])
        safe = []
        for field_name, description in descriptions.items():
            if self._field_is_sensitive(field_name, description):
                continue
            field = model._fields.get(field_name)
            if field and field.comodel_name and (
                field.comodel_name in _BLOCKED_MODELS
                or field.comodel_name.startswith('mcp.')
            ):
                continue
            if (
                policy['allowed_fields']
                and field_name not in policy['allowed_fields']
                and field_name not in ('id', 'display_name')
            ):
                continue
            if field_name in policy['blocked_fields']:
                continue
            if write and (
                description.get('readonly')
                or field_name in (
                    'id', 'display_name', 'create_uid', 'create_date',
                    'write_uid', 'write_date',
                )
            ):
                continue
            safe.append(field_name)
        if requested is None or requested == []:
            if write or all_fields:
                return safe
            defaults = [name for name in ('id', 'display_name') if name in safe]
            return defaults or safe[:10]
        if not isinstance(requested, list) or any(not isinstance(name, str) for name in requested):
            raise ValidationError(_('Fields must be an array of field names.'))
        unavailable = set(requested) - set(safe)
        if unavailable:
            raise AccessError(_('These fields are unavailable through MCP: %s', ', '.join(sorted(unavailable))))
        return list(dict.fromkeys(requested))

    def _field_is_sensitive(self, field_name, description):
        return (
            self._field_name_is_sensitive(field_name)
            or description.get('type') == 'binary'
        )

    def _field_name_is_sensitive(self, field_name):
        return field_name in _BLOCKED_FIELDS or bool(_SENSITIVE_FIELD_RE.search(field_name))

    def _safe_values(self, model, values, *, records=None):
        if not isinstance(values, dict) or not values:
            raise ValidationError(_('Values must be a non-empty object.'))
        safe = set(self._safe_fields(model, write=True))
        unavailable = set(values) - safe
        if unavailable:
            raise AccessError(_('These fields cannot be written through MCP: %s', ', '.join(sorted(unavailable))))
        for field_name, value in values.items():
            self._validate_write_value(
                model,
                model._fields[field_name],
                value,
                values=values,
                records=records,
            )
        if records:
            for field in model._fields.values():
                if (
                    field.type == 'many2one_reference'
                    and field.model_field in values
                    and field.name not in values
                ):
                    for record in records:
                        value = record[field.name]
                        if value:
                            self._validate_write_value(
                                model,
                                field,
                                value,
                                values=values,
                                records=record,
                            )
        return values

    def _validate_write_value(self, model, field, value, *, values=None, records=None):
        """Validate relational writes so nested ORM commands cannot bypass MCP policy."""
        if value in (False, None):
            return
        gateway = self.with_env(model.env)
        if field.type == 'many2one':
            related_model, _policy = gateway._get_model(field.comodel_name, 'read')
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValidationError(_('Many2one values must be positive integer record IDs.'))
            record_id = value
            related = related_model.browse(record_id).exists()
            self._ensure_complete(related, [record_id])
            related.check_access('read')
            return
        if field.type == 'reference':
            if not isinstance(value, str) or ',' not in value:
                raise ValidationError(_('Reference values must use the "model,id" format.'))
            model_name, raw_id = value.rsplit(',', 1)
            related_model, _policy = gateway._get_model(model_name, 'read')
            try:
                record_id = int(raw_id)
            except ValueError as error:
                raise ValidationError(_('Reference values must contain a numeric record ID.')) from error
            related = related_model.browse(record_id).exists()
            self._ensure_complete(related, [record_id])
            related.check_access('read')
            return
        if field.type == 'many2one_reference':
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValidationError(_(
                    'Many2one reference values must be positive integer record IDs.'
                ))
            model_names = self._many2one_reference_models(
                model,
                field,
                values or {},
                records=records,
            )
            if not model_names:
                raise ValidationError(_(
                    'The target model for the many2one reference could not be determined.'
                ))
            for model_name in model_names:
                related_model, _policy = gateway._get_model(model_name, 'read')
                related = related_model.browse(value).exists()
                self._ensure_complete(related, [value])
                related.check_access('read')
            return
        if field.type not in ('one2many', 'many2many'):
            return
        if not isinstance(value, (list, tuple)):
            raise ValidationError(_('Relational fields must use ORM command arrays.'))

        for command in value:
            if not isinstance(command, (list, tuple)) or not command:
                raise ValidationError(_('Invalid relational command.'))
            if isinstance(command[0], bool) or not isinstance(command[0], int):
                raise ValidationError(_('Invalid relational command operation.'))
            operation = command[0]
            if operation == 0:  # Command.create(values)
                if len(command) < 3 or not isinstance(command[2], dict):
                    raise ValidationError(_('Relational create commands require a values object.'))
                related_model, _policy = gateway._get_model(field.comodel_name, 'create')
                gateway._safe_values(related_model, command[2])
            elif operation == 1:  # Command.update(id, values)
                if len(command) < 3 or not isinstance(command[2], dict):
                    raise ValidationError(_('Relational update commands require an ID and values object.'))
                related_model, _policy = gateway._get_model(field.comodel_name, 'update')
                record_id = self._record_ids([command[1]])[0]
                related = related_model.browse(record_id).exists()
                self._ensure_complete(related, [record_id])
                related.check_access('write')
                gateway._safe_values(related_model, command[2], records=related)
            elif operation == 2:  # Command.delete(id)
                raise AccessError(_(
                    'Nested relational deletes are not allowed; use delete preview '
                    'and confirmation on the related model.'
                ))
            elif operation == 3:  # Command.unlink(id)
                if field.type == 'one2many':
                    raise AccessError(_('One2many unlink commands are not allowed through MCP.'))
                related_model, _policy = gateway._get_model(field.comodel_name, 'read')
                record_id = self._record_ids([command[1]])[0]
                related = related_model.browse(record_id).exists()
                self._ensure_complete(related, [record_id])
                related.check_access('read')
            elif operation == 4:  # Command.link(id)
                required_operation = 'update' if field.type == 'one2many' else 'read'
                related_model, _policy = gateway._get_model(field.comodel_name, required_operation)
                record_id = self._record_ids([command[1]])[0]
                related = related_model.browse(record_id).exists()
                self._ensure_complete(related, [record_id])
                related.check_access('write' if field.type == 'one2many' else 'read')
            elif operation == 5:  # Command.clear()
                if field.type == 'one2many':
                    raise AccessError(_('One2many clear commands are not allowed through MCP.'))
            elif operation == 6:  # Command.set(ids)
                if field.type == 'one2many':
                    raise AccessError(_('One2many set commands are not allowed through MCP.'))
                if len(command) < 3 or not isinstance(command[2], (list, tuple)):
                    raise ValidationError(_('Relational set commands require an ID array.'))
                related_model, _policy = gateway._get_model(field.comodel_name, 'read')
                record_ids = self._record_ids(list(command[2])) if command[2] else []
                related = related_model.browse(record_ids).exists()
                self._ensure_complete(related, record_ids)
                related.check_access('read')
            else:
                raise ValidationError(_('Unsupported relational command operation: %s', operation))

    def _many2one_reference_models(self, model, field, values, *, records=None):
        """Resolve the model half of a pseudo-relation without using sudo."""
        model_field_name = field.model_field
        if model_field_name in values:
            model_name = values[model_field_name]
            if not isinstance(model_name, str) or not model_name:
                raise ValidationError(_('A many2one reference target model is required.'))
            return {model_name}

        if records:
            model_names = {
                record[model_field_name]
                for record in records
                if record[model_field_name]
            }
            if model_names:
                if any(not isinstance(model_name, str) for model_name in model_names):
                    raise ValidationError(_('Invalid many2one reference target model.'))
                return model_names

        model_field = model._fields.get(model_field_name)
        related_path = tuple(model_field.related or ()) if model_field else ()
        if len(related_path) < 2 or related_path[0] not in values:
            return set()
        source_field = model._fields.get(related_path[0])
        source_id = values[related_path[0]]
        if (
            not source_field or source_field.type != 'many2one'
            or isinstance(source_id, bool) or not isinstance(source_id, int)
            or source_id <= 0
        ):
            return set()
        source_model, _policy = self._get_model(source_field.comodel_name, 'read')
        source = source_model.browse(source_id).exists()
        self._ensure_complete(source, [source_id])
        source.check_access('read')
        resolved = source
        for path_part in related_path[1:]:
            if not isinstance(resolved, models.BaseModel) or len(resolved) != 1:
                return set()
            path_field = resolved._fields.get(path_part)
            if not path_field or not resolved._has_field_access(path_field, 'read'):
                raise AccessError(_('The many2one reference target model is not accessible.'))
            resolved = resolved[path_part]
            if isinstance(resolved, models.BaseModel) and resolved:
                self._get_model(resolved._name, 'read')
                resolved.check_access('read')
        return {resolved} if isinstance(resolved, str) and resolved else set()

    def _with_safe_context(self, model, context):
        safe_context = self._normalize_context(context)
        return model.with_context(**safe_context) if safe_context else model

    def _normalize_context(self, context):
        if not context:
            return {}
        if not isinstance(context, dict):
            raise ValidationError(_('Context must be an object.'))
        unknown = set(context) - _SAFE_CONTEXT_KEYS
        if unknown:
            raise ValidationError(_('Unsupported context keys: %s', ', '.join(sorted(unknown))))
        safe_context = dict(context)
        if 'allowed_company_ids' in safe_context:
            raw_company_ids = safe_context['allowed_company_ids']
            if (
                not isinstance(raw_company_ids, list)
                or any(isinstance(company_id, bool) or not isinstance(company_id, int)
                       for company_id in raw_company_ids)
            ):
                raise ValidationError(_('Allowed company IDs must be an array of integers.'))
            requested = set(raw_company_ids)
            allowed = set(self.env.user.company_ids.ids)
            if not requested or not requested <= allowed:
                raise AccessError(_('The requested company context is not available to this user.'))
            safe_context['allowed_company_ids'] = sorted(requested)
        return safe_context

    def _allowed_view_types(self):
        values = self.env['ir.ui.view']._fields['type'].get_values(self.env)
        return set(values) - {'qweb'}

    def _validate_domain(self, model, domain):
        """Reject domains which could use blocked fields as predicate side channels."""
        if not isinstance(domain, (list, tuple)):
            raise ValidationError(_('Domain must be an array.'))

        def visit(current_model, node):
            if not isinstance(node, (list, tuple)):
                raise ValidationError(_('Invalid domain expression.'))
            is_condition = (
                len(node) == 3
                and isinstance(node[0], str)
                and node[0] not in ('&', '|', '!')
                and isinstance(node[1], str)
            )
            if is_condition:
                relation_model, final_field = self._validate_field_path(current_model, node[0])
                if node[1] == 'any!':
                    raise AccessError(_('The record-rule-bypassing any! operator is not available through MCP.'))
                if node[1] in ('any', 'not any'):
                    if not final_field.comodel_name:
                        raise ValidationError(_('The any operator requires a relational field.'))
                    related_model, _policy = self._get_model(final_field.comodel_name, 'read')
                    visit(related_model, node[2])
                return
            for item in node:
                if isinstance(item, str):
                    if item not in ('&', '|', '!'):
                        raise ValidationError(_('Invalid domain operator.'))
                else:
                    visit(current_model, item)

        visit(model, domain)

    def _validate_field_path(self, model, field_path):
        if not isinstance(field_path, str) or not field_path:
            raise ValidationError(_('Invalid field path.'))
        current_model = model
        parts = field_path.split('.')
        for index, field_name in enumerate(parts):
            safe_fields = set(self._safe_fields(current_model, all_fields=True))
            if field_name not in safe_fields:
                raise AccessError(_('An unavailable field was used in a domain or order.'))
            field = current_model._fields.get(field_name)
            if not field:
                raise ValidationError(_('Unknown field in domain or order.'))
            if index < len(parts) - 1:
                if not field.comodel_name:
                    raise ValidationError(_('Only relational fields can be traversed.'))
                current_model, _policy = self._get_model(field.comodel_name, 'read')
        return current_model, field

    def _validate_order(self, model, order, allowed_specs=None):
        if not order:
            return
        if not isinstance(order, str) or len(order) > 1000:
            raise ValidationError(_('Order must be a valid string.'))
        pattern = re.compile(
            r'^([A-Za-z_][A-Za-z0-9_.]*(?::[A-Za-z_][A-Za-z0-9_]*)?)'
            r'(?:\s+(?:ASC|DESC))?(?:\s+NULLS\s+(?:FIRST|LAST))?$',
            re.IGNORECASE,
        )
        for item in order.split(','):
            match = pattern.match(item.strip())
            if not match:
                raise ValidationError(_('Invalid order expression.'))
            field_spec = match.group(1)
            if allowed_specs is not None and field_spec in allowed_specs:
                continue
            if ':' in field_spec:
                raise AccessError(_('An unavailable aggregate was used for ordering.'))
            self._validate_field_path(model, field_spec)

    def _validate_group_specs(self, model, groupby, aggregates):
        for spec in groupby:
            if not isinstance(spec, str):
                raise ValidationError(_('Group-by specifications must be strings.'))
            match = re.fullmatch(
                r'([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)'
                r'(?::[A-Za-z_][A-Za-z0-9_]*)?',
                spec,
            )
            if not match:
                raise ValidationError(_('Invalid group-by specification.'))
            try:
                self._validate_field_path(model, match.group(1))
            except AccessError:
                raise AccessError(_('An unavailable field was used for grouping.'))
        for spec in aggregates:
            if spec == '__count':
                continue
            if not isinstance(spec, str):
                raise ValidationError(_('Aggregate specifications must be strings.'))
            match = re.fullmatch(
                r'([A-Za-z_][A-Za-z0-9_]*):([A-Za-z_][A-Za-z0-9_]*)',
                spec,
            )
            if not match:
                raise ValidationError(_('Invalid aggregate specification.'))
            if match.group(1) not in set(self._safe_fields(model, all_fields=True)):
                raise AccessError(_('An unavailable field was used for aggregation.'))

    def _action_arguments(self, model, policy, arguments):
        method_name = arguments.get('method')
        if (
            not isinstance(method_name, str) or not method_name
            or method_name.startswith('_') or method_name in _FORBIDDEN_WORKFLOW_METHODS
            or method_name not in policy['workflow_methods']
        ):
            raise AccessError(_('The workflow method is not allowlisted for MCP.'))
        try:
            method = get_public_method(model, method_name)
        except (AccessError, AttributeError) as error:
            raise AccessError(_('The configured workflow method is not remotely callable.')) from error
        if getattr(method, '_api_model', False):
            raise AccessError(_('Model-level methods cannot be exposed as record workflow actions.'))
        args = arguments.get('args') or []
        kwargs = arguments.get('kwargs') or {}
        if not isinstance(args, list) or not isinstance(kwargs, dict):
            raise ValidationError(_('Workflow args must be an array and kwargs must be an object.'))
        return method_name, args, kwargs

    def _report_allowed(self, report):
        report.check_access('read')
        return not report.group_ids or bool(report.group_ids & self.env.user.all_group_ids)

    def _record_ids(self, values):
        if not isinstance(values, list) or not values:
            raise ValidationError(_('At least one record ID is required.'))
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValidationError(_('Record IDs must be positive integers.'))
        record_ids = list(dict.fromkeys(values))
        if any(record_id <= 0 for record_id in record_ids):
            raise ValidationError(_('Record IDs must be positive integers.'))
        max_ids = self._global_page_size()
        if len(record_ids) > max_ids:
            raise ValidationError(_('Too many record IDs; the configured maximum is %s.', max_ids))
        return record_ids

    def _ensure_complete(self, records, requested_ids):
        if set(records.ids) != set(requested_ids):
            raise MissingError(_('One or more requested records do not exist.'))

    def _page_limit(self, requested=None, policy=None):
        maximum = self._global_page_size()
        if policy:
            maximum = min(maximum, policy['max_results'])
        if requested is None:
            return maximum
        try:
            requested = int(requested)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('Limit must be an integer.')) from error
        if requested <= 0:
            raise ValidationError(_('Limit must be positive.'))
        return min(requested, maximum)

    def _global_page_size(self):
        return self._integer_param('mcp.max_page_size', 100, minimum=1, maximum=1000)

    def _integer_param(self, key, default, *, minimum, maximum):
        try:
            value = int(self.env['ir.config_parameter'].sudo().get_param(key, default))
        except (TypeError, ValueError):
            value = default
        return min(max(value, minimum), maximum)

    def _make_cursor(self, kind, offset, fingerprint=None):
        return hash_sign(
            self.sudo().env, 'mcp.cursor',
            {'kind': kind, 'offset': offset, 'fingerprint': fingerprint},
            expiration=datetime.timedelta(minutes=10),
        )

    def _cursor_offset(self, cursor, kind, fingerprint=None):
        if not cursor:
            return 0
        try:
            payload = verify_hash_signed(self.sudo().env, 'mcp.cursor', cursor)
        except (TypeError, ValueError, UnicodeError):
            payload = None
        if (
            not payload or payload.get('kind') != kind
            or payload.get('fingerprint') != fingerprint
            or not isinstance(payload.get('offset'), int) or payload['offset'] < 0
        ):
            raise ValidationError(self.env._('The pagination cursor is invalid or expired.'))
        return payload['offset']

    def _bound_cursor(self, cursor, kind, fingerprint):
        return self._cursor_offset(cursor, kind, fingerprint) if cursor else 0

    def _digest(self, value):
        return __import__('hashlib').sha256(
            json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()
        ).hexdigest()

    def _json_safe(self, value):
        if isinstance(value, models.BaseModel):
            return {'model': value._name, 'ids': value.ids}
        if isinstance(value, Markup):
            return str(value)
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        if isinstance(value, decimal.Decimal):
            return float(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            content = bytes(value)
            resource = self.env['mcp.download.token'].issue(
                'mcp-binary-output.bin',
                mimetype='application/octet-stream',
                payload=base64.b64encode(content),
            )
            return {'binaryResource': resource, 'size': len(content)}
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    def _tool_result(self, data):
        text = self._bounded_json(data)
        return {
            'content': [{
                'type': 'text',
                'text': text,
            }],
            'structuredContent': data,
        }

    def _resource_result(self, uri, data):
        safe = self._json_safe(data)
        return {'contents': [{
            'uri': uri, 'mimeType': 'application/json',
            'text': self._bounded_json(safe),
        }]}

    def _bounded_json(self, value):
        text = json.dumps(
            value, ensure_ascii=False, separators=(',', ':'), default=str,
        )
        maximum = self._integer_param(
            'mcp.max_response_bytes', 1_048_576,
            minimum=1024, maximum=16 * 1024 * 1024,
        )
        if len(text.encode('utf-8')) > maximum:
            raise ValidationError(_(
                'The MCP result exceeds the configured response limit. '
                'Request fewer records or fields.'
            ))
        return text
