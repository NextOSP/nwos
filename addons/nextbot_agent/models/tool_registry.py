# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import csv
import io
import json
import logging
import re

from markupsafe import Markup

from nwos import _, models
from nwos.exceptions import AccessError, UserError, ValidationError
from nwos.tools import html2plaintext
from nwos.tools.misc import formatLang


_logger = logging.getLogger(__name__)

_SENSITIVE_KEY = re.compile(
    r'(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|session)',
    re.IGNORECASE,
)

_BLOCKED_READ_MODELS = {
    'auth.oauth.provider',
    'ir.config_parameter',
    'mcp.confirmation.token',
    'mcp.download.token',
    'nextbot.approval',
    'payment.token',
    'res.users.apikeys',
    'res.users.apikeys.description',
    'res.users.apikeys.show',
}

_PRODUCT_CREATE_MODELS = {'product.template', 'product.product'}


class NextBotToolRegistry(models.AbstractModel):
    """Extensible registry for NextBot tools.

    Addons can inherit this model and extend ``_get_tool_providers``. A provider
    contains an OpenAI-compatible ``definition``, an ``access`` classification,
    and an executor method name. Write providers may additionally implement a
    preparer. Provider results must be JSON serializable.

    There is no per-tool configuration: tools run with the requesting user's
    environment, so the standard record ACLs and record rules decide what each
    account can read, and every write requires an explicit user approval.
    """

    _name = 'nextbot.tool.registry'
    _description = 'NextBot Tool Registry'

    def _get_tool_providers(self):
        definitions = {
            item.get('function', {}).get('name'): item
            for item in self.env['mail.bot']._ai_tool_definitions()
            if item.get('function', {}).get('name')
        }
        definitions.setdefault('prepare_partner_source_tag', {
            'type': 'function',
            'function': {
                'name': 'prepare_partner_source_tag',
                'description': (
                    'Prepare assigning a source tag to an existing customer. '
                    'Requires explicit user approval.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'partner_id': {'type': 'integer'},
                        'source_name': {'type': 'string'},
                    },
                    'required': ['partner_id', 'source_name'],
                },
            },
        })
        definitions.setdefault('render_report', {
            'type': 'function',
            'function': {
                'name': 'render_report',
                'description': (
                    "Render a record's printable PDF report (e.g. a quotation, invoice, or "
                    "delivery slip) and attach it to the chat as a downloadable file. "
                    "Use this whenever the user asks to export, print, or get a PDF of a record."
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'model': {'type': 'string'},
                        'res_id': {'type': 'integer'},
                        'report_name': {
                            'type': 'string',
                            'description': 'Optional report name filter when the model has several print reports.',
                        },
                    },
                    'required': ['model', 'res_id'],
                },
            },
        })
        definitions.setdefault('aggregate_records', {
            'type': 'function',
            'function': {
                'name': 'aggregate_records',
                'description': (
                    'Group and aggregate ERP records (like a pivot/BI query): counts, sums, '
                    'averages per group. Use for questions like revenue by customer, orders '
                    'per salesperson, doanh thu theo khách hàng.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'model': {'type': 'string'},
                        'domain': {'type': 'array'},
                        'groupby': {
                            'type': 'array', 'items': {'type': 'string'},
                            'description': "Fields to group by, e.g. ['partner_id'] or ['user_id','state'].",
                        },
                        'aggregates': {
                            'type': 'array', 'items': {'type': 'string'},
                            'description': "Numeric fields to sum, e.g. ['amount_total']. Count is always included.",
                        },
                    },
                    'required': ['model', 'groupby'],
                },
            },
        })
        definitions.setdefault('export_records', {
            'type': 'function',
            'function': {
                'name': 'export_records',
                'description': (
                    'Export ERP records to a downloadable CSV file (opens in Excel). '
                    'Use when the user asks to export/download a list, xuất excel/csv.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'model': {'type': 'string'},
                        'domain': {'type': 'array'},
                        'fields': {'type': 'array', 'items': {'type': 'string'}},
                        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 2000},
                        'filename': {'type': 'string'},
                    },
                    'required': ['model'],
                },
            },
        })
        definitions.setdefault('prepare_confirm_sale_order', {
            'type': 'function',
            'function': {
                'name': 'prepare_confirm_sale_order',
                'description': (
                    'Prepare confirming a draft/sent quotation into a sales order '
                    '(xác nhận báo giá). Requires user confirmation.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'res_id': {'type': 'integer', 'description': 'The sale.order id.'},
                    },
                    'required': ['res_id'],
                },
            },
        })
        definitions.setdefault('prepare_schedule_activity', {
            'type': 'function',
            'function': {
                'name': 'prepare_schedule_activity',
                'description': (
                    'Prepare scheduling a to-do/reminder activity on a record for the current '
                    'user (e.g. follow up with a customer on a date). Requires user confirmation.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'model': {'type': 'string'},
                        'res_id': {'type': 'integer'},
                        'summary': {'type': 'string'},
                        'note': {'type': 'string'},
                        'date_deadline': {'type': 'string', 'description': 'YYYY-MM-DD'},
                    },
                    'required': ['model', 'res_id', 'summary'],
                },
            },
        })
        definitions.setdefault('list_calendar_events', {
            'type': 'function',
            'function': {
                'name': 'list_calendar_events',
                'description': (
                    "List the user's calendar events/meetings in a date range "
                    "(agenda, lịch họp). Defaults to the next 7 days."
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'date_from': {'type': 'string', 'description': 'YYYY-MM-DD'},
                        'date_to': {'type': 'string', 'description': 'YYYY-MM-DD'},
                    },
                },
            },
        })
        definitions.setdefault('prepare_create_calendar_event', {
            'type': 'function',
            'function': {
                'name': 'prepare_create_calendar_event',
                'description': (
                    'Prepare creating a calendar event/meeting for the current user '
                    '(đặt lịch, tạo cuộc họp). Times are in the user timezone. '
                    'Requires user confirmation.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'start': {'type': 'string', 'description': 'YYYY-MM-DD HH:MM in the user timezone.'},
                        'duration_hours': {'type': 'number', 'minimum': 0.25, 'maximum': 24},
                        'description': {'type': 'string'},
                        'location': {'type': 'string'},
                    },
                    'required': ['name', 'start'],
                },
            },
        })
        definitions.setdefault('web_search', {
            'type': 'function',
            'function': {
                'name': 'web_search',
                'description': (
                    'Search the public web for current information (news, prices, '
                    'suppliers, regulations) and return a summary with source URLs. '
                    'Use only when ERP data cannot answer the question.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                    },
                    'required': ['query'],
                },
            },
        })
        definitions.setdefault('find_models', {
            'type': 'function',
            'function': {
                'name': 'find_models',
                'description': 'Discover accessible ERP models by technical name or business label before guessing a model.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 30},
                    },
                    'required': ['query'],
                },
            },
        })
        definitions.setdefault('describe_model', {
            'type': 'function',
            'function': {
                'name': 'describe_model',
                'description': (
                    'Inspect an accessible ERP model schema: field names, labels, types, '
                    'required/read-only flags, relations, and selection values. Use before generic writes.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'model': {'type': 'string'},
                        'fields': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': ['model'],
                },
            },
        })
        definitions.setdefault('prepare_create_records', {
            'type': 'function',
            'function': {
                'name': 'prepare_create_records',
                'description': (
                    'Prepare creating 1 to 100 records of one ERP model in one grouped approval. '
                    'Use describe_model first and use this instead of repeated create calls. '
                    'Product creates automatically skip existing internal references, barcodes, '
                    'and exact names when no stronger identifier is supplied.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'model': {'type': 'string'},
                        'records': {'type': 'array', 'items': {'type': 'object'}},
                    },
                    'required': ['model', 'records'],
                },
            },
        })
        definitions.setdefault('prepare_update_records', {
            'type': 'function',
            'function': {
                'name': 'prepare_update_records',
                'description': (
                    'Prepare different updates to 1 to 100 records in one grouped approval. '
                    'Each item has res_id and values.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'model': {'type': 'string'},
                        'records': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'res_id': {'type': 'integer'},
                                    'values': {'type': 'object'},
                                },
                                'required': ['res_id', 'values'],
                            },
                        },
                    },
                    'required': ['model', 'records'],
                },
            },
        })
        read_handlers = {
            'check_stock': '_execute_mail_bot_read',
            'search_records': '_execute_mail_bot_read',
            'read_record': '_execute_mail_bot_read',
            'sales_report': '_execute_mail_bot_read',
            'sale_quotation_search': '_execute_mail_bot_read',
            'render_report': '_execute_render_report',
            'aggregate_records': '_execute_aggregate_records',
            'export_records': '_execute_export_records',
            'list_calendar_events': '_execute_list_calendar_events',
            'web_search': '_execute_web_search',
            'find_models': '_execute_find_models',
            'describe_model': '_execute_describe_model',
        }
        write_names = {
            'prepare_create_sale_quotation',
            'prepare_post_comment',
            'prepare_create_record',
            'prepare_update_record',
            'prepare_text_attachment',
            'prepare_partner_source_tag',
            'prepare_mass_update',
            'prepare_confirm_sale_order',
            'prepare_schedule_activity',
            'prepare_create_calendar_event',
            'prepare_create_records',
            'prepare_update_records',
        }
        providers = {
            name: {
                'definition': definitions[name],
                'access': 'read',
                'executor': handler,
                'card_type': 'tool_result',
                'parallel_safe': True,
                'idempotent': True,
            }
            for name, handler in read_handlers.items()
            if name in definitions
        }
        providers.update({
            name: {
                'definition': definitions[name],
                'access': 'write',
                'preparer': '_prepare_mail_bot_write',
                'executor': '_execute_mail_bot_write',
                'card_type': 'approval',
                'parallel_safe': False,
                'idempotent': False,
            }
            for name in write_names
            if name in definitions
        })
        return providers

    def _get_provider(self, tool_name):
        """Return the provider for ``tool_name``.

        Every tool is available to every internal user: the tools execute with
        the requesting user's environment, so the regular record ACLs and
        record rules are the only access control. Writes always go through the
        explicit approval flow.
        """
        provider = self._get_tool_providers().get(tool_name)
        if not provider:
            raise UserError(_('Unsupported NextBot tool: %s', tool_name))
        return provider

    def effective_access(self, tool_name, provider=None):
        provider = provider or self._get_provider(tool_name)
        return 'write' if provider.get('access') == 'write' else 'read'

    def requires_approval(self, tool_name, provider=None):
        return self.effective_access(tool_name, provider) == 'write'

    def get_definitions(self, access=None):
        return [
            provider['definition']
            for provider in self._get_tool_providers().values()
            if not access or self.effective_access(
                provider['definition'].get('function', {}).get('name'), provider,
            ) == access
        ]

    def get_metadata(self):
        result = []
        for name, provider in self._get_tool_providers().items():
            definition = provider['definition'].get('function', {})
            result.append({
                'name': name,
                'description': definition.get('description') or '',
                'access': self.effective_access(name, provider),
                'approval_required': self.requires_approval(name, provider),
                'card_type': provider.get('card_type') or 'tool_result',
                'parallel_safe': bool(provider.get('parallel_safe')),
                'idempotent': bool(provider.get('idempotent')),
            })
        return result

    def validate_arguments(self, tool_name, arguments):
        provider = self._get_provider(tool_name)
        if not isinstance(arguments, dict):
            raise ValidationError(_('Tool arguments must be a JSON object.'))
        try:
            encoded = json.dumps(arguments, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('Tool arguments are not JSON serializable.')) from error
        if len(encoded) > 64_000:
            raise ValidationError(_('Tool arguments are too large.'))
        schema = provider['definition'].get('function', {}).get('parameters') or {}
        self._validate_schema(arguments, schema, path='arguments', depth=0)
        return arguments

    def _validate_schema(self, value, schema, path, depth):
        if depth > 8:
            raise ValidationError(_('Tool arguments are nested too deeply.'))
        expected = schema.get('type')
        type_checks = {
            'object': lambda candidate: isinstance(candidate, dict),
            'array': lambda candidate: isinstance(candidate, list),
            'string': lambda candidate: isinstance(candidate, str),
            'integer': lambda candidate: isinstance(candidate, int) and not isinstance(candidate, bool),
            'number': lambda candidate: isinstance(candidate, (int, float)) and not isinstance(candidate, bool),
            'boolean': lambda candidate: isinstance(candidate, bool),
        }
        if expected in type_checks and not type_checks[expected](value):
            raise ValidationError(_('%s must be of type %s.', path, expected))
        if 'enum' in schema and value not in schema['enum']:
            raise ValidationError(_('%s has an unsupported value.', path))
        if expected in ('integer', 'number'):
            if 'minimum' in schema and value < schema['minimum']:
                raise ValidationError(_('%s is below the minimum value.', path))
            if 'maximum' in schema and value > schema['maximum']:
                raise ValidationError(_('%s is above the maximum value.', path))
        if expected == 'object':
            for required in schema.get('required', []):
                if required not in value:
                    raise ValidationError(_('Missing required tool argument: %s', required))
            properties = schema.get('properties') or {}
            for key, child in value.items():
                if key in properties:
                    self._validate_schema(child, properties[key], '%s.%s' % (path, key), depth + 1)
        elif expected == 'array' and schema.get('items'):
            for index, child in enumerate(value):
                self._validate_schema(child, schema['items'], '%s[%s]' % (path, index), depth + 1)

    def prepare_write(self, tool_name, arguments, run):
        provider = self._get_provider(tool_name)
        arguments = self.validate_arguments(tool_name, arguments)
        if not self.requires_approval(tool_name, provider):
            raise ValidationError(_('%s does not require approval.', tool_name))
        preparer = provider.get('preparer')
        if not preparer:
            return {
                'arguments': arguments,
                'summary': _('Approve running %s.', tool_name.replace('_', ' ')),
                'summary_html': '',
            }
        prepared, summary_html = getattr(self, preparer)(tool_name, arguments, run)
        summary_text = html2plaintext(str(summary_html or '')).strip()
        return {
            'arguments': prepared,
            'summary': summary_text[:4000],
            'summary_html': str(summary_html or ''),
        }

    def execute(self, tool_name, arguments, run):
        provider = self._get_provider(tool_name)
        arguments = self.validate_arguments(tool_name, arguments)
        executor = provider.get('executor')
        if not executor:
            raise UserError(_('NextBot tool %s has no executor.', tool_name))
        result = getattr(self, executor)(tool_name, arguments, run)
        return self._json_result(result, tool_name)

    def _execute_mail_bot_read(self, tool_name, arguments, run):
        arguments = self._guard_read_arguments(tool_name, arguments)
        return self.env['mail.bot']._ai_execute_tool(tool_name, arguments)

    def _guard_read_arguments(self, tool_name, arguments):
        if tool_name not in ('search_records', 'read_record'):
            return arguments
        arguments = dict(arguments)
        model_name = str(arguments.get('model') or '').strip()
        if model_name in _BLOCKED_READ_MODELS or model_name.endswith('.token'):
            raise AccessError(_('NextBot cannot read credential or token models.'))
        if model_name not in self.env:
            return arguments
        Model = self.env[model_name]
        safe_fields = []
        for field_name in arguments.get('fields') or []:
            field = Model._fields.get(field_name) if isinstance(field_name, str) else None
            if not field or field.type == 'binary' or _SENSITIVE_KEY.search(field_name):
                continue
            safe_fields.append(field_name)
        arguments['fields'] = safe_fields
        if tool_name == 'search_records':
            for leaf in self._domain_leaves(arguments.get('domain') or []):
                field_name = leaf[0] if leaf and isinstance(leaf[0], str) else ''
                if field_name and _SENSITIVE_KEY.search(field_name):
                    raise AccessError(_('NextBot cannot query secret fields.'))
        return arguments

    def _domain_leaves(self, domain):
        for item in domain if isinstance(domain, list) else []:
            if isinstance(item, (list, tuple)) and len(item) >= 3 and isinstance(item[0], str):
                yield item
            elif isinstance(item, list):
                yield from self._domain_leaves(item)

    def _create_identity_pairs(self, Model, values):
        """Return stable business identifiers used to de-duplicate agent creates."""
        if Model._name not in _PRODUCT_CREATE_MODELS or not isinstance(values, dict):
            return []
        identities = []
        for field_name in ('default_code', 'barcode'):
            value = values.get(field_name)
            if field_name in Model._fields and isinstance(value, str) and value.strip():
                identities.append((field_name, value.strip().casefold()))
        if not identities:
            value = values.get('name')
            if 'name' in Model._fields and isinstance(value, str) and value.strip():
                identities.append(('name', ' '.join(value.split()).casefold()))
        return identities

    def _dedupe_create_records(self, Model, records):
        """Split proposed product creates into new rows and explainable skips."""
        if Model._name not in _PRODUCT_CREATE_MODELS:
            return list(records), []
        candidate_pairs = {
            pair
            for values in records
            for pair in self._create_identity_pairs(Model, values)
        }
        existing_by_pair = {}
        if candidate_pairs:
            leaves = [
                (field_name, '=ilike', normalized)
                for field_name, normalized in sorted(candidate_pairs)
            ]
            domain = leaves if len(leaves) == 1 else ['|'] * (len(leaves) - 1) + leaves
            existing = Model.with_context(active_test=False).search(domain, limit=500)
            for record in existing:
                for field_name, _normalized in candidate_pairs:
                    if field_name not in record._fields:
                        continue
                    value = record[field_name]
                    if not isinstance(value, str) or not value.strip():
                        continue
                    normalized = (
                        ' '.join(value.split()).casefold()
                        if field_name == 'name'
                        else value.strip().casefold()
                    )
                    pair = (field_name, normalized)
                    if pair in candidate_pairs:
                        existing_by_pair.setdefault(pair, record)

        accepted = []
        skipped = []
        accepted_by_pair = {}
        for index, values in enumerate(records):
            pairs = self._create_identity_pairs(Model, values)
            matched_record = next(
                (existing_by_pair[pair] for pair in pairs if pair in existing_by_pair),
                False,
            )
            matched_values = next(
                (accepted_by_pair[pair] for pair in pairs if pair in accepted_by_pair),
                False,
            )
            if matched_record or matched_values:
                matched_name = matched_record.display_name if matched_record else (
                    matched_values.get('name') or matched_values.get('default_code') or _('Earlier item in this request')
                )
                skipped.append({
                    'index': index,
                    'name': values.get('name') or values.get('display_name') or values.get('default_code') or _('Unnamed record'),
                    'default_code': values.get('default_code') or False,
                    'barcode': values.get('barcode') or False,
                    'reason': 'already_exists' if matched_record else 'duplicate_in_request',
                    'matched_id': matched_record.id if matched_record else False,
                    'matched_name': matched_name,
                })
                continue
            accepted.append(values)
            for pair in pairs:
                accepted_by_pair[pair] = values
        return accepted, skipped

    def _lock_create_identities(self, Model, records):
        """Serialize competing NextBot product creates with the same identifiers."""
        lock_keys = sorted({
            '%s:%s:%s' % (Model._name, field_name, normalized)
            for values in records
            for field_name, normalized in self._create_identity_pairs(Model, values)
        })
        for lock_key in lock_keys:
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', [lock_key])

    def _prepare_mail_bot_write(self, tool_name, arguments, run):
        bot = self.env['mail.bot']
        prepared = dict(arguments)
        if tool_name == 'prepare_create_sale_quotation':
            prepared = bot._ai_prepare_sale_quotation_arguments(prepared)
            if prepared.get('error'):
                raise UserError(prepared['error'])
            if prepared.get('missing'):
                raise UserError(_('The quotation request is missing required customer or product information.'))
        elif tool_name == 'prepare_partner_source_tag':
            prepared = bot._ai_prepare_partner_source_tag_arguments(prepared)
            if prepared.get('error'):
                raise UserError(prepared['error'])
        elif tool_name in ('prepare_create_record', 'prepare_update_record', 'prepare_mass_update'):
            prepared['values'] = bot._ai_clean_values(prepared.get('values'))
            sensitive_fields = [
                field_name
                for field_name in prepared['values']
                if _SENSITIVE_KEY.search(field_name)
            ]
            if sensitive_fields:
                raise AccessError(_(
                    'NextBot cannot change password, credential, token, or secret fields.'
                ))
            if tool_name == 'prepare_mass_update':
                mass_model = str(prepared.get('model') or '').strip()
                if mass_model in _BLOCKED_READ_MODELS or mass_model.endswith('.token'):
                    raise AccessError(_('NextBot cannot change credential or token models.'))
                # Fail early (count, cap, write access) so the approval card is honest.
                bot._ai_resolve_mass_update_records(prepared)
        elif tool_name in ('prepare_create_records', 'prepare_update_records'):
            model_name = str(prepared.get('model') or '').strip()
            Model = self._guard_generic_model(model_name)
            records = prepared.get('records') or []
            if not isinstance(records, list) or not 1 <= len(records) <= 100:
                raise ValidationError(_('Bulk operations require between 1 and 100 records.'))
            cleaned = []
            for item in records:
                if not isinstance(item, dict):
                    raise ValidationError(_('Every bulk-operation item must be an object.'))
                values = bot._ai_clean_values(
                    item.get('values') if tool_name == 'prepare_update_records' else item
                )
                if any(_SENSITIVE_KEY.search(field_name) for field_name in values):
                    raise AccessError(_('NextBot cannot change credential, token, or secret fields.'))
                unknown = [field_name for field_name in values if field_name not in Model._fields]
                if unknown:
                    raise ValidationError(_('Unknown fields on %(model)s: %(fields)s', model=model_name, fields=', '.join(unknown)))
                if tool_name == 'prepare_update_records':
                    record = Model.browse(int(item.get('res_id') or 0)).exists()
                    if not record:
                        raise UserError(_('Record not found: %s', item.get('res_id')))
                    record.check_access('write')
                    cleaned.append({'res_id': record.id, 'values': values})
                else:
                    Model.check_access('create')
                    cleaned.append(values)
            duplicate_report = list(prepared.get('duplicate_report') or [])
            if tool_name == 'prepare_create_records':
                cleaned, duplicates = self._dedupe_create_records(Model, cleaned)
                duplicate_report.extend(duplicates)
            prepared['records'] = cleaned
            if duplicate_report:
                prepared['duplicate_report'] = duplicate_report
            summary = _(
                '%(action)s %(count)s %(model)s record(s)%(skipped)s.',
                action=_('Create') if tool_name == 'prepare_create_records' else _('Update'),
                count=len(cleaned),
                model=Model._description or Model._name,
                skipped=_('; skip %s duplicate(s) already in ERP', len(duplicate_report))
                if duplicate_report else '',
            )
            return prepared, Markup.escape(summary)

        if tool_name == 'prepare_confirm_sale_order':
            prepared['model'] = 'sale.order'
        if tool_name == 'prepare_create_calendar_event':
            # Fail early on unparsable times so the approval card is honest.
            bot._ai_parse_calendar_event_arguments(prepared)
        model_name = str(prepared.get('model') or '').strip()
        if tool_name in {
            'prepare_post_comment', 'prepare_create_record',
            'prepare_update_record', 'prepare_text_attachment',
            'prepare_confirm_sale_order', 'prepare_schedule_activity',
        }:
            if model_name not in self.env:
                raise UserError(_('Model not found: %s', model_name))
            if model_name in _BLOCKED_READ_MODELS or model_name.endswith('.token'):
                raise AccessError(_('NextBot cannot change credential or token models.'))
            Model = self.env[model_name]
            if tool_name == 'prepare_create_record':
                Model.check_access('create')
            else:
                record = Model.browse(int(prepared.get('res_id') or 0)).exists()
                if not record:
                    raise UserError(_('Record not found.'))
                record.check_access(
                    'read'
                    if tool_name in ('prepare_post_comment', 'prepare_schedule_activity')
                    else 'write'
                )
            if tool_name == 'prepare_text_attachment' and len(str(prepared.get('content') or '')) > 100_000:
                raise ValidationError(_('Generated text attachments are limited to 100,000 characters.'))

        action = {'tool': tool_name, 'arguments': prepared}
        summary_html = bot._ai_pending_action_summary(action)
        if not isinstance(summary_html, Markup):
            summary_html = Markup.escape(str(summary_html or ''))
        return prepared, summary_html

    def _execute_find_models(self, tool_name, arguments, run):
        query = str(arguments.get('query') or '').strip()
        limit = min(max(int(arguments.get('limit') or 15), 1), 30)
        models = self.env['ir.model'].search([
            '|', ('model', 'ilike', query), ('name', 'ilike', query),
        ], limit=limit * 3)
        result = []
        for model in models:
            if model.model in _BLOCKED_READ_MODELS or model.model.endswith('.token'):
                continue
            try:
                self.env[model.model].check_access('read')
            except (AccessError, KeyError):
                continue
            result.append({'model': model.model, 'label': model.name})
            if len(result) >= limit:
                break
        return {'models': result}

    def _execute_describe_model(self, tool_name, arguments, run):
        Model = self._guard_generic_model(arguments.get('model'))
        requested = arguments.get('fields') or []
        names = requested if requested else list(Model._fields)
        fields_result = []
        for name in names[:200]:
            field = Model._fields.get(name) if isinstance(name, str) else None
            if not field or field.type == 'binary' or _SENSITIVE_KEY.search(name):
                continue
            selection = getattr(field, 'selection', False)
            if callable(selection):
                try:
                    selection = selection(Model)
                except Exception:  # noqa: BLE001 - optional schema detail
                    selection = []
            fields_result.append({
                'name': name,
                'label': field.string,
                'type': field.type,
                'required': bool(field.required),
                'readonly': bool(field.readonly),
                'relation': getattr(field, 'comodel_name', False) or False,
                'selection': selection if isinstance(selection, (list, tuple)) else False,
            })
        return {
            'model': Model._name,
            'label': Model._description,
            'fields': fields_result,
        }

    def _guard_generic_model(self, model_name):
        model_name = str(model_name or '').strip()
        if model_name not in self.env:
            raise UserError(_('Model not found: %s', model_name))
        if model_name in _BLOCKED_READ_MODELS or model_name.endswith('.token'):
            raise AccessError(_('NextBot cannot read credential or token models.'))
        Model = self.env[model_name]
        Model.check_access('read')
        return Model

    def _execute_aggregate_records(self, tool_name, arguments, run):
        Model = self._guard_generic_model(arguments.get('model'))
        domain = arguments.get('domain') or []
        if not isinstance(domain, list):
            return {'error': 'Domain must be a list.'}
        groupby = [
            field for field in (arguments.get('groupby') or [])
            if isinstance(field, str) and field.split(':')[0] in Model._fields
        ][:3]
        if not groupby:
            return {'error': 'No valid groupby fields.'}
        aggregates = [
            field for field in (arguments.get('aggregates') or [])
            if isinstance(field, str) and field in Model._fields
            and Model._fields[field].type in ('integer', 'float', 'monetary')
        ][:5]
        read_fields = aggregates + [field.split(':')[0] for field in groupby]
        try:
            groups = Model.read_group(domain, read_fields, groupby, lazy=False, limit=80)
        except (ValueError, KeyError) as error:
            return {'error': 'Aggregation failed: %s' % error}
        rows = []
        for group in groups:
            row = {'count': group.get('__count', 0)}
            for field in groupby:
                value = group.get(field)
                row[field.split(':')[0]] = value[1] if isinstance(value, tuple) else value
            for field in aggregates:
                row[field] = group.get(field)
            rows.append(row)
        return {
            'model': Model._name,
            'groupby': groupby,
            'aggregates': aggregates,
            'group_count': len(rows),
            'rows': rows,
        }

    def _execute_export_records(self, tool_name, arguments, run):
        Model = self._guard_generic_model(arguments.get('model'))
        domain = arguments.get('domain') or []
        if not isinstance(domain, list):
            return {'error': 'Domain must be a list.'}
        bot = self.env['mail.bot']
        field_names = bot._ai_clean_read_fields(Model, arguments.get('fields'))
        limit = min(max(int(arguments.get('limit') or 500), 1), 2000)
        records = Model.search_read(domain, field_names, limit=limit)
        if not records:
            return {'error': 'No records match the export selection.'}
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        columns = list(records[0].keys())
        writer.writerow(columns)
        for record in records:
            writer.writerow([
                value[1] if isinstance(value, tuple) else value
                for value in (record.get(column) for column in columns)
            ])
        filename = str(arguments.get('filename') or '%s export' % (Model._description or Model._name))
        filename = re.sub(r'[\\/:*?"<>|]+', '-', filename)[:100]
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        raw = buffer.getvalue().encode('utf-8-sig')  # BOM so Excel opens UTF-8 correctly
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'raw': raw,
            'mimetype': 'text/csv',
            'res_model': run._name,
            'res_id': run.id,
        })
        artifact = self.env['nextbot.artifact'].sudo().create({
            'name': filename,
            'artifact_type': 'file',
            'run_id': run.id,
            'attachment_id': attachment.id,
            'mimetype': 'text/csv',
            'byte_size': len(raw),
            'resource_model': Model._name,
        })
        run._add_event('artifact.created', {'artifact': artifact._serialize()})
        return {
            'text': 'Exported %s records to %s.' % (len(records), filename),
            'exported_count': len(records),
            'artifact_id': artifact.id,
            'download_url': '/web/content/%s?download=true' % attachment.id,
            'card': {
                'id': 'run-%s-export-%s' % (run.id, artifact.id),
                'type': 'artifact',
                'title': filename,
                'subtitle': _('%s records', len(records)),
                'mimetype': 'text/csv',
                'size': len(raw),
                'download_url': '/web/content/%s?download=true' % attachment.id,
            },
        }

    def _execute_list_calendar_events(self, tool_name, arguments, run):
        if 'calendar.event' not in self.env:
            return {'error': 'Calendar is not installed.'}
        Event = self.env['calendar.event']
        Event.check_access('read')
        import pytz
        from datetime import datetime, timedelta
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

        def parse_day(value, fallback):
            value = str(value or '').strip()
            if not value:
                return fallback
            try:
                return tz.localize(datetime.strptime(value, '%Y-%m-%d'))
            except ValueError:
                return fallback

        date_from = parse_day(arguments.get('date_from'), today)
        date_to = parse_day(arguments.get('date_to'), date_from + timedelta(days=7))
        date_to = date_to + timedelta(days=1)  # inclusive end day
        events = Event.search([
            ('start', '>=', date_from.astimezone(pytz.utc).replace(tzinfo=None)),
            ('start', '<', date_to.astimezone(pytz.utc).replace(tzinfo=None)),
        ], order='start', limit=50)
        rows = []
        for event in events:
            start_local = pytz.utc.localize(event.start).astimezone(tz)
            rows.append({
                'id': event.id,
                'name': event.name,
                'start': start_local.strftime('%Y-%m-%d %H:%M'),
                'duration_hours': event.duration,
                'location': event.location or '',
                'attendees': ', '.join(event.partner_ids.mapped('display_name')[:5]),
            })
        return {
            'timezone': str(tz),
            'event_count': len(rows),
            'events': rows,
        }

    def _execute_web_search(self, tool_name, arguments, run):
        query = str(arguments.get('query') or '').strip()
        if not query:
            return {'error': 'Missing query.'}
        bot = self.env['mail.bot']
        settings = bot._ai_get_settings()
        if not settings:
            return {'error': 'The AI provider is not configured.'}
        if 'openrouter' not in str(settings.get('endpoint') or '').lower():
            return {'error': 'Web search is only available with the OpenRouter provider.'}
        model = str(settings.get('model') or '')
        online_model = model if model.endswith(':online') else model.split(':')[0] + ':online'
        payload = {
            'model': online_model,
            'messages': [{
                'role': 'user',
                'content': 'Search the web and answer concisely with source URLs: %s' % query,
            }],
        }
        response = bot._ai_chat_request(dict(settings, model=online_model), payload)
        message = bot._ai_chat_message_from_json(response.json())
        content = bot._ai_stream_text(message.get('content')) or ''
        sources = []
        for annotation in message.get('annotations') or []:
            citation = annotation.get('url_citation') if isinstance(annotation, dict) else None
            if isinstance(citation, dict) and citation.get('url'):
                source = {
                    'title': citation.get('title') or citation['url'],
                    'url': citation['url'],
                }
                sources.append(source)
                run._add_event('source.created', {'source': source})
        return {
            'query': query,
            'text': content[:6000],
            'sources': sources[:10],
        }

    def _execute_render_report(self, tool_name, arguments, run):
        model_name = str(arguments.get('model') or '').strip()
        if model_name not in self.env:
            return {'error': 'Unknown model %s.' % model_name}
        if model_name in _BLOCKED_READ_MODELS or model_name.endswith('.token'):
            raise AccessError(_('NextBot cannot read credential or token models.'))
        record = self.env[model_name].browse(int(arguments.get('res_id') or 0)).exists()
        if not record:
            return {'error': 'Record not found.'}
        record.check_access('read')

        Report = self.env['ir.actions.report']
        domain = [('model', '=', model_name), ('report_type', '=', 'qweb-pdf')]
        # Order by id: the module's primary report (e.g. "Quotation") predates
        # extras like "PRO-FORMA Invoice"; default name-ordering picks wrongly.
        reports = Report.search(domain, order='id')
        report_query = str(arguments.get('report_name') or '').strip()
        if report_query and reports:
            matching = reports.filtered(
                lambda candidate: report_query.lower() in (candidate.name or '').lower()
                or report_query.lower() in (candidate.report_name or '').lower()
            )
            reports = matching or reports
        if not reports:
            return {'error': 'No PDF report is defined for %s.' % model_name}
        report = reports[0]

        try:
            pdf_content, _report_type = Report._render_qweb_pdf(report.id, [record.id])
        except Exception as error:  # noqa: BLE001 - wkhtmltopdf can fail/hang-recover; degrade to a tool error
            _logger.warning('NextBot render_report failed for %s,%s: %s', model_name, record.id, error)
            return {'error': 'The PDF report could not be rendered: %s' % error}

        filename = '%s - %s.pdf' % (report.name, record.display_name)
        filename = re.sub(r'[\\/:*?"<>|]+', '-', filename)[:120]
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'raw': pdf_content,
            'mimetype': 'application/pdf',
            'res_model': run._name,
            'res_id': run.id,
        })
        artifact = self.env['nextbot.artifact'].sudo().create({
            'name': filename,
            'artifact_type': 'file',
            'run_id': run.id,
            'attachment_id': attachment.id,
            'mimetype': 'application/pdf',
            'byte_size': len(pdf_content),
            'resource_model': model_name,
            'resource_id': record.id,
        })
        run._add_event('artifact.created', {'artifact': artifact._serialize()})
        return {
            'text': 'Generated %s (%s bytes).' % (filename, len(pdf_content)),
            'artifact_id': artifact.id,
            'download_url': '/web/content/%s?download=true' % attachment.id,
            'card': {
                'id': 'run-%s-report-%s' % (run.id, artifact.id),
                'type': 'artifact',
                'title': filename,
                'subtitle': record.display_name,
                'mimetype': 'application/pdf',
                'size': len(pdf_content),
                'download_url': '/web/content/%s?download=true' % attachment.id,
                'res_model': model_name,
                'res_id': record.id,
            },
        }

    def _execute_mail_bot_write(self, tool_name, arguments, run):
        if tool_name == 'prepare_create_records':
            Model = self._guard_generic_model(arguments.get('model'))
            Model.check_access('create')
            proposed = arguments.get('records') or []
            self._lock_create_identities(Model, proposed)
            to_create, runtime_duplicates = self._dedupe_create_records(Model, proposed)
            skipped = list(arguments.get('duplicate_report') or []) + runtime_duplicates
            records = Model.create(to_create) if to_create else Model.browse()
            record_summaries = []
            for record in records[:100]:
                summary = {'id': record.id, 'display_name': record.display_name}
                for field_name in ('name', 'default_code', 'barcode'):
                    if field_name in record._fields and record[field_name]:
                        summary[field_name] = record[field_name]
                record_summaries.append(summary)
            return {
                'text': _(
                    'Created %(created)s record(s); skipped %(skipped)s duplicate(s).',
                    created=len(records),
                    skipped=len(skipped),
                ),
                'model': Model._name,
                'created_count': len(records),
                'skipped_count': len(skipped),
                'skipped_records': self.redact(skipped[:100]),
                'record_ids': records.ids,
                'records': record_summaries,
            }
        if tool_name == 'prepare_update_records':
            Model = self._guard_generic_model(arguments.get('model'))
            updated = []
            for item in arguments.get('records') or []:
                record = Model.browse(int(item.get('res_id') or 0)).exists()
                if not record:
                    raise UserError(_('Record not found: %s', item.get('res_id')))
                record.check_access('write')
                record.write(item.get('values') or {})
                updated.append({'id': record.id, 'display_name': record.display_name})
            return {
                'text': _('Updated %s records.', len(updated)),
                'model': Model._name,
                'record_ids': [record['id'] for record in updated],
                'records': updated,
            }
        channel = run.conversation_id.channel_id
        result = self.env['mail.bot']._ai_execute_pending_action(
            {'tool': tool_name, 'arguments': arguments},
            channel=channel,
        )
        if isinstance(result, Markup):
            result = {
                'text': html2plaintext(str(result)).strip(),
                'html': str(result),
            }
        if isinstance(result, dict) and not result.get('card'):
            record = self.env['mail.bot']._ai_load_last_record(channel)
            card = self._write_result_card(record, run) if record else False
            if card:
                result['card'] = card
        return result

    def approval_preview(self, tool_name, prepared):
        """Structured preview the workspace renders on the pending-approval card."""
        bot = self.env['mail.bot']
        if tool_name == 'prepare_create_sale_quotation' and 'sale.order' in self.env:
            partner = self.env['res.partner'].browse(int(prepared.get('partner_id') or 0)).exists()
            currency = self.env.company.currency_id
            lines = []
            total = 0.0
            for line in prepared.get('order_lines') or []:
                product = self.env['product.product'].browse(int(line.get('product_id') or 0)).exists()
                if not product:
                    continue
                quantity = float(line.get('quantity') or 0.0)
                subtotal = product.lst_price * quantity
                total += subtotal
                lines.append({
                    'name': product.display_name,
                    'quantity': quantity,
                    'price_unit': formatLang(self.env, product.lst_price, currency_obj=currency),
                    'subtotal': formatLang(self.env, subtotal, currency_obj=currency),
                })
            return {
                'type': 'quotation',
                'title': _('Quotation ready to create'),
                'customer': partner.display_name if partner else str(prepared.get('partner_name') or ''),
                'formatted_total': formatLang(self.env, total, currency_obj=currency),
                'lines': lines[:10],
            }
        if tool_name == 'prepare_mass_update':
            try:
                records = bot._ai_resolve_mass_update_records(prepared)
            except (AccessError, UserError, ValidationError):
                return False
            return {
                'type': 'mass_update',
                'title': _('Mass update %s records', len(records)),
                'model': records._name,
                'model_label': self.env[records._name]._description or records._name,
                'count': len(records),
                'sample': records[:10].mapped('display_name'),
                'values': self.redact(prepared.get('values') or {}),
            }
        if tool_name in ('prepare_create_records', 'prepare_update_records'):
            records = prepared.get('records') or []
            duplicates = prepared.get('duplicate_report') or []
            model_name = prepared.get('model')
            Model = self.env[model_name] if model_name in self.env else False
            return {
                'type': 'bulk_change',
                'action': 'create' if tool_name == 'prepare_create_records' else 'update',
                'title': _(
                    'Create %s new records' if tool_name == 'prepare_create_records' else 'Update %s records',
                    len(records),
                ),
                'model': model_name,
                'model_label': (Model._description or Model._name) if Model else model_name,
                'count': len(records),
                'sample': self.redact(records[:10]),
                'skipped_count': len(duplicates),
                'skipped_sample': self.redact(duplicates[:10]),
            }
        return False

    def _write_result_card(self, record, run, title=None):
        """Structured card for a record a tool touched or found."""
        card_id = 'run-%s-write-%s-%s' % (run.id, record._name, record.id)
        if record._name == 'sale.order':
            currency = record.currency_id or self.env.company.currency_id
            return {
                'id': card_id,
                'type': 'quotation',
                'title': title or (_('Order confirmed') if record.state == 'sale' else _('Quotation created')),
                'subtitle': record.name,
                'reference': record.name,
                'customer': record.partner_id.display_name,
                'formatted_total': formatLang(
                    self.env, record.amount_total, currency_obj=currency,
                ),
                'lines': [
                    {
                        'name': line.product_id.display_name or line.name,
                        'quantity': line.product_uom_qty,
                        'price_unit': formatLang(
                            self.env, line.price_unit, currency_obj=currency,
                        ),
                        'subtotal': formatLang(
                            self.env, line.price_subtotal, currency_obj=currency,
                        ),
                    }
                    for line in record.order_line[:10]
                ],
                'res_model': 'sale.order',
                'res_id': record.id,
            }
        return {
            'id': card_id,
            'type': 'record',
            'title': record.display_name,
            'subtitle': record._description or record._name,
            'res_model': record._name,
            'res_id': record.id,
        }

    def _json_result(self, result, tool_name):
        try:
            encoded = json.dumps(result, ensure_ascii=False, default=str)
            decoded = self.redact(json.loads(encoded))
            encoded = json.dumps(decoded, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('NextBot tool %s returned an invalid result.', tool_name)) from error
        limit = 6000
        if len(encoded) > limit:
            return {
                'truncated': True,
                'preview': encoded[:limit].rstrip(),
                'original_size': len(encoded),
            }
        return decoded

    def result_card(self, tool_name, arguments, result, run):
        """Build the stable, safe card projection for built-in read tools."""
        if not isinstance(result, dict):
            return False
        if tool_name in ('render_report', 'export_records') and isinstance(result.get('card'), dict):
            return result['card']
        if tool_name == 'list_calendar_events' and result.get('events'):
            return {
                'id': 'run-%s-tool-%s' % (run.id, run.tool_call_count),
                'type': 'report',
                'title': _('Calendar events'),
                'summary': _('%s events', result.get('event_count') or 0),
                'res_model': 'calendar.event',
                'rows': result.get('events') or [],
                'columns': [
                    {'key': 'name', 'label': _('Event')},
                    {'key': 'start', 'label': _('Start')},
                    {'key': 'duration_hours', 'label': _('Hours')},
                    {'key': 'location', 'label': _('Location')},
                    {'key': 'attendees', 'label': _('Attendees')},
                ],
            }
        if tool_name == 'aggregate_records' and result.get('rows'):
            return {
                'id': 'run-%s-tool-%s' % (run.id, run.tool_call_count),
                'type': 'report',
                'title': _('Aggregation: %s', str(result.get('model') or '')),
                'summary': _('%s groups', result.get('group_count') or 0),
                'rows': result.get('rows') or [],
            }
        card_id = 'run-%s-tool-%s' % (run.id, run.tool_call_count)
        if result.get('error'):
            return {
                'id': card_id,
                'type': 'error',
                'title': _('%s failed', tool_name.replace('_', ' ').title()),
                'summary': str(result['error'])[:1000],
            }
        if tool_name == 'check_stock':
            return {
                'id': card_id,
                'type': 'report',
                'title': _('Stock availability'),
                'summary': _('%s products found', len(result.get('products') or [])),
                'res_model': 'product.product',
                'rows': result.get('products') or [],
                'columns': [
                    {'key': 'name', 'label': _('Product')},
                    {'key': 'default_code', 'label': _('SKU')},
                    {'key': 'qty_available', 'label': _('On hand')},
                    {'key': 'free_qty', 'label': _('Free')},
                    {'key': 'virtual_available', 'label': _('Forecast')},
                    {'key': 'uom', 'label': _('Unit')},
                ],
            }
        if tool_name == 'search_records':
            records = result.get('records') or []
            model_name = str(arguments.get('model') or '')
            total = result.get('total_count')
            if model_name == 'sale.order' and len(records) == 1 and records[0].get('id'):
                # A single quotation deserves the rich business card, not a table.
                record = self.env['sale.order'].browse(int(records[0]['id'])).exists()
                if record:
                    card = self._write_result_card(record, run, title=record.name)
                    card['id'] = card_id
                    state_labels = dict(record._fields['state'].selection)
                    card['subtitle'] = state_labels.get(record.state, record.state)
                    return card
            return {
                'id': card_id,
                'type': 'report',
                'title': _('ERP records'),
                'subtitle': model_name,
                'summary': _('%s of %s records', len(records), total if total is not None else len(records)),
                'res_model': model_name,
                'rows': records,
            }
        if tool_name == 'read_record':
            record = result.get('record') or {}
            return {
                'id': card_id,
                'type': 'record',
                'title': record.get('display_name') or _('ERP record'),
                'fields': record,
                'res_model': str(arguments.get('model') or ''),
                'res_id': int(record.get('id') or arguments.get('res_id') or 0),
            }
        if tool_name == 'sales_report':
            return {
                'id': card_id,
                'type': 'report',
                'title': _('Sales report: %s', result.get('period_label') or result.get('period') or ''),
                'subtitle': result.get('total_formatted') or '',
                'summary': _('%s confirmed orders', result.get('order_count') or 0),
                'res_model': 'sale.order',
                'rows': result.get('orders') or [],
                'columns': [
                    {'key': 'name', 'label': _('Order')},
                    {'key': 'customer', 'label': _('Customer')},
                    {'key': 'state_label', 'label': _('Status')},
                    {'key': 'amount_formatted', 'label': _('Total')},
                    {'key': 'date_order', 'label': _('Date')},
                ],
            }
        if tool_name == 'sale_quotation_search':
            quotations = result.get('quotations') or []
            return {
                'id': card_id,
                'type': 'report',
                'title': _('Matching quotations'),
                'subtitle': result.get('query') or '',
                'summary': _('%s quotations found', result.get('total_count') or len(quotations)),
                'res_model': 'sale.order',
                'rows': quotations,
                'columns': [
                    {'key': 'name', 'label': _('Quotation')},
                    {'key': 'customer', 'label': _('Customer')},
                    {'key': 'state_label', 'label': _('Status')},
                    {'key': 'amount_formatted', 'label': _('Total')},
                ],
            }
        return False

    def redact(self, value, depth=0):
        """Return a safe event/card representation, never provider secrets."""
        if depth > 8:
            return '[nested data omitted]'
        if isinstance(value, dict):
            return {
                str(key): ('[redacted]' if _SENSITIVE_KEY.search(str(key)) else self.redact(child, depth + 1))
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [self.redact(child, depth + 1) for child in value[:100]]
        if isinstance(value, str) and len(value) > 4000:
            return value[:4000] + '…'
        return value
