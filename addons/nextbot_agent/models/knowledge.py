# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import logging

from nwos import _, api, fields, models
from nwos.modules import module as module_tools
from nwos.modules.db import FunctionStatus

_logger = logging.getLogger(__name__)

CHUNK_TARGET_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150
CHUNK_MAX_PER_ATTACHMENT = 500
CHANNEL_ATTACHMENTS_PER_PASS = 10


class NextBotKnowledgeDocument(models.Model):
    """Organization knowledge uploaded by administrators for NextBot RAG."""

    _name = 'nextbot.knowledge.document'
    _description = 'NextBot Knowledge Document'
    _order = 'id desc'

    name = fields.Char(required=True)
    file = fields.Binary(attachment=True, required=True)
    file_name = fields.Char()
    company_id = fields.Many2one(
        'res.company', index=True,
        help='Leave empty to share the document with every company.',
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('indexed', 'Indexed'),
        ('failed', 'Failed'),
    ], default='pending', index=True, readonly=True)
    error_message = fields.Char(readonly=True)
    chunk_count = fields.Integer(readonly=True)
    active = fields.Boolean(default=True)
    chunk_ids = fields.One2many('nextbot.knowledge.chunk', 'document_id')

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        documents._request_reindex()
        return documents

    def write(self, values):
        result = super().write(values)
        if 'file' in values:
            self._request_reindex()
        if values.get('active') is False:
            self.sudo().chunk_ids.unlink()
            self.sudo().write({'state': 'pending', 'chunk_count': 0})
        return result

    def action_reindex(self):
        self._request_reindex()
        return True

    def _request_reindex(self):
        self.sudo().chunk_ids.unlink()
        self.sudo().write({'state': 'pending', 'error_message': False, 'chunk_count': 0})
        for document in self.filtered('active'):
            try:
                document.sudo()._index_now()
            except Exception:  # noqa: BLE001 - the cron retries pending documents
                _logger.warning('NextBot knowledge indexing deferred for %s', document.name, exc_info=True)

    def _get_attachment(self):
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', 'file'),
        ], limit=1)

    def _index_now(self):
        self.ensure_one()
        attachment = self._get_attachment()
        if not attachment:
            self.write({'state': 'failed', 'error_message': _('No stored file found.')})
            return
        chunks = self.env['nextbot.knowledge.chunk']._rebuild_for_attachment(
            attachment, document=self,
        )
        if not chunks:
            self.write({
                'state': 'failed',
                'error_message': _(
                    'No text could be extracted. Install the attachment_indexation '
                    'module dependencies (pdfminer, python-docx) for PDF/Office files.'
                ),
                'chunk_count': 0,
            })
            return
        self.write({'state': 'indexed', 'error_message': False, 'chunk_count': len(chunks)})

    @api.model
    def _cron_index_knowledge(self, batch_size=10):
        documents = self.sudo().search([('state', '=', 'pending')], limit=batch_size, order='id')
        committable = not module_tools.current_test
        for document in documents:
            try:
                with self.env.cr.savepoint():
                    document._index_now()
            except Exception:  # noqa: BLE001 - one document must not block the batch
                _logger.warning('NextBot knowledge indexing failed for %s', document.name, exc_info=True)
                document.write({'state': 'failed', 'error_message': _('Indexing failed; check server logs.')})
            if committable:
                self.env.cr.commit()


class NextBotKnowledgeChunk(models.Model):
    """Retrievable text chunk extracted from an attachment.

    Access model: rows are system-only; every user-facing read goes through
    nextbot.retrieval which access-checks the source attachment as the
    requesting user. Record rules cannot express "attachment readable", so we
    do not pretend otherwise.
    """

    _name = 'nextbot.knowledge.chunk'
    _description = 'NextBot Knowledge Chunk'
    _order = 'attachment_id, sequence'

    attachment_id = fields.Many2one('ir.attachment', required=True, index=True, ondelete='cascade')
    document_id = fields.Many2one('nextbot.knowledge.document', index=True, ondelete='cascade')
    channel_id = fields.Many2one('discuss.channel', index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', index=True)
    sequence = fields.Integer(default=0)
    content = fields.Text(required=True)
    checksum = fields.Char(index=True)

    _scope_required = models.Constraint(
        'CHECK (document_id IS NOT NULL OR channel_id IS NOT NULL)',
        'A knowledge chunk must belong to a document or a conversation.',
    )

    def init(self):
        if self.env.registry.has_trigram:
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS nextbot_knowledge_chunk_content_trgm
                ON nextbot_knowledge_chunk USING gin (lower(content) gin_trgm_ops)
            """)
            if self.env.registry.has_unaccent == FunctionStatus.INDEXABLE:
                self.env.cr.execute("""
                    CREATE INDEX IF NOT EXISTS nextbot_knowledge_chunk_content_unaccent_trgm
                    ON nextbot_knowledge_chunk USING gin (unaccent(lower(content)) gin_trgm_ops)
                """)

    @api.model
    def _attachment_text(self, attachment):
        text = (attachment.index_content or '').strip()
        if text:
            return text
        mimetype = str(attachment.mimetype or '')
        if mimetype.startswith('text/') or mimetype in ('application/json', 'application/xml'):
            try:
                return (attachment.raw or b'').decode('utf-8', errors='ignore').strip()
            except Exception:  # noqa: BLE001
                return ''
        return ''

    @api.model
    def _split_text(self, text):
        """Paragraph-aware chunks of ~CHUNK_TARGET_CHARS with a small overlap."""
        text = '\n'.join(line.strip() for line in str(text or '').splitlines())
        chunks = []
        position = 0
        length = len(text)
        while position < length and len(chunks) < CHUNK_MAX_PER_ATTACHMENT:
            end = min(position + CHUNK_TARGET_CHARS, length)
            if end < length:
                # Prefer to cut on a paragraph, then a sentence, then a space.
                window = text[position:end]
                for separator in ('\n\n', '\n', '. ', ' '):
                    cut = window.rfind(separator)
                    if cut > CHUNK_TARGET_CHARS // 2:
                        end = position + cut + len(separator)
                        break
            chunk = text[position:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= length:
                break
            position = max(end - CHUNK_OVERLAP_CHARS, position + 1)
        return chunks

    @api.model
    def _rebuild_for_attachment(self, attachment, document=None, channel=None):
        self.sudo().search([('attachment_id', '=', attachment.id)]).unlink()
        text = self._attachment_text(attachment)
        if not text:
            return self.browse()
        values = []
        for sequence, content in enumerate(self._split_text(text)):
            values.append({
                'attachment_id': attachment.id,
                'document_id': document.id if document else False,
                'channel_id': channel.id if channel else False,
                'company_id': document.company_id.id if document else False,
                'sequence': sequence,
                'content': content,
                'checksum': attachment.checksum or '',
            })
        return self.sudo().create(values)

    @api.model
    def _ensure_channel_attachments(self, channel, limit=CHANNEL_ATTACHMENTS_PER_PASS):
        """Lazily (re)chunk conversation uploads whose content changed."""
        if not channel:
            return
        attachments = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'discuss.channel'),
            ('res_id', '=', channel.id),
        ], order='id desc', limit=50)
        rebuilt = 0
        for attachment in attachments:
            if rebuilt >= limit:
                break
            existing = self.sudo().search_count([
                ('attachment_id', '=', attachment.id),
                ('checksum', '=', attachment.checksum or ''),
            ])
            if existing:
                continue
            self._rebuild_for_attachment(attachment, channel=channel)
            rebuilt += 1
