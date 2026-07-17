# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import _, api, fields, models
from nwos.exceptions import ValidationError


class NextBotOrgRule(models.Model):
    """Administrator-written standing instructions for NextBot.

    Active rules are always injected into the system prompt (never merely
    retrieved), so the assistant follows them on every request. Rules without
    a company apply to every company.
    """

    _name = 'nextbot.org.rule'
    _description = 'NextBot Organization Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    content = fields.Text(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', index=True,
        help='Leave empty to apply the rule in every company.',
    )

    @api.constrains('content')
    def _check_content(self):
        for rule in self:
            content = (rule.content or '').strip()
            if not content:
                raise ValidationError(_('An organization rule cannot be empty.'))
            if len(content) > 1000:
                raise ValidationError(_('Keep each organization rule under 1,000 characters.'))

    @api.model
    def _prompt_block(self, limit_chars=2000):
        """Render the active rules for the current companies as numbered lines."""
        rules = self.sudo().search([
            '|',
            ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ])
        lines = []
        used = 0
        for index, rule in enumerate(rules, start=1):
            line = '%s. %s' % (index, ' '.join((rule.content or '').split()))
            if used + len(line) + 1 > limit_chars:
                lines.append(_('(more rules omitted)'))
                break
            lines.append(line)
            used += len(line) + 1
        return '\n'.join(lines)
