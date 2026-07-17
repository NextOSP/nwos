# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import fields, models


class NextBotArtifact(models.Model):
    _name = 'nextbot.artifact'
    _description = 'NextBot Artifact'
    _order = 'id desc'

    name = fields.Char(required=True)
    artifact_type = fields.Selection([
        ('text', 'Text'),
        ('markdown', 'Markdown'),
        ('json', 'JSON'),
        ('table', 'Table'),
        ('file', 'File'),
        ('record_collection', 'Record Collection'),
    ], required=True, default='text', index=True)
    run_id = fields.Many2one('nextbot.run', required=True, ondelete='cascade', index=True)
    conversation_id = fields.Many2one(
        related='run_id.conversation_id', store=True, readonly=True, index=True,
    )
    user_id = fields.Many2one(
        related='run_id.user_id', store=True, readonly=True, index=True,
    )
    content = fields.Text()
    data = fields.Json(default=dict)
    attachment_id = fields.Many2one('ir.attachment', ondelete='set null')
    mimetype = fields.Char()
    byte_size = fields.Integer()
    resource_model = fields.Char()
    resource_id = fields.Integer()

    def _serialize(self, include_content=False):
        self.ensure_one()
        result = {
            'id': self.id,
            'run_id': self.run_id.id,
            'conversation_id': self.conversation_id.id,
            'name': self.name,
            'type': self.artifact_type,
            'mimetype': self.mimetype or (self.attachment_id.mimetype if self.attachment_id else False),
            'size': self.byte_size or (self.attachment_id.file_size if self.attachment_id else 0),
            'attachment_id': self.attachment_id.id or False,
            'download_url': (
                '/web/content/%s?download=true' % self.attachment_id.id
                if self.attachment_id else False
            ),
            'resource': (
                {'model': self.resource_model, 'id': self.resource_id}
                if self.resource_model and self.resource_id else False
            ),
        }
        if include_content:
            result.update({
                'content': self.content or '',
                'data': self.data or {},
            })
        return result

