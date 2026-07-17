# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import Command, _, api, fields, models
from nwos.exceptions import AccessError, ValidationError

from ..utils import iso_utc


ACTIVE_RUN_STATUSES = (
    'queued', 'planning', 'running', 'waiting_input', 'waiting_approval', 'verifying',
)


class NextBotConversation(models.Model):
    _name = 'nextbot.conversation'
    _description = 'NextBot Conversation'
    _order = 'last_activity_at desc, id desc'

    name = fields.Char(required=True, default=lambda self: _('New conversation'))
    active = fields.Boolean(default=True, index=True)
    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env.user,
    )
    channel_id = fields.Many2one(
        'discuss.channel', required=True, ondelete='restrict', index=True,
    )
    last_activity_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    last_run_id = fields.Many2one('nextbot.run', ondelete='set null', copy=False)
    run_ids = fields.One2many('nextbot.run', 'conversation_id')

    _user_channel_unique = models.Constraint(
        'UNIQUE(user_id, channel_id)',
        'A Discuss conversation can only be linked once per user.',
    )

    @api.model
    def _get_or_create_for_user(self, name=None, reactivate=True):
        """Import the current user's legacy direct NextBot chat, if any.

        This is only used for backward compatibility: it never creates a new
        Discuss DM with the bot (NextBot no longer lives in Discuss). New
        workspace conversations use private Discuss groups so users can create
        more than one thread.
        """
        user = self.env.user
        bot_partner = self.env.ref('base.partner_root')
        channel = self.env['discuss.channel'].sudo().search([
            ('channel_type', '=', 'chat'),
            ('channel_member_ids', 'any', [('partner_id', '=', bot_partner.id)]),
            ('channel_member_ids', 'any', [('partner_id', '=', user.partner_id.id)]),
        ], limit=1)
        if not channel:
            return self.browse()
        conversation = self.sudo().with_context(active_test=False).search([
            ('user_id', '=', user.id),
            ('channel_id', '=', channel.id),
        ], limit=1)
        values = {}
        if not conversation:
            conversation = self.sudo().create({
                'name': (name or '').strip() or _('New conversation'),
                'user_id': user.id,
                'channel_id': channel.id,
            })
        else:
            if reactivate and not conversation.active:
                values['active'] = True
            if name and name.strip():
                values['name'] = name.strip()[:120]
            if values:
                conversation.sudo().write(values)
        return conversation.with_user(user)

    @api.model
    def _create_for_user(self, name=None):
        """Create a distinct private Discuss-backed workspace conversation."""
        user = self.env.user
        bot_partner = self.env.ref('base.partner_root')
        title = (name or '').strip()[:120] or _('New conversation')
        channel = self.env['discuss.channel'].create({
            'name': _('NextBot: %s', title),
            'channel_type': 'group',
            'channel_member_ids': [
                Command.create({'partner_id': user.partner_id.id}),
                Command.create({'partner_id': bot_partner.id}),
            ],
        })
        return self.sudo().create({
            'name': title,
            'user_id': user.id,
            'channel_id': channel.id,
        }).with_user(user)

    def _ensure_current_user(self):
        bot_partner = self.env.ref('base.partner_root')
        for conversation in self:
            if conversation.user_id != self.env.user:
                raise AccessError(_('You cannot access this NextBot conversation.'))
            member_partner_ids = conversation.channel_id.sudo().channel_member_ids.partner_id.ids
            if self.env.user.partner_id.id not in member_partner_ids or bot_partner.id not in member_partner_ids:
                raise AccessError(_('You are not a member of this NextBot conversation.'))
        return True

    def _touch(self, run=None):
        values = {'last_activity_at': fields.Datetime.now()}
        if run:
            values['last_run_id'] = run.id
        self.sudo().write(values)

    def _ensure_no_active_runs(self):
        active = self.env['nextbot.run'].sudo().search([
            ('conversation_id', 'in', self.ids),
            ('status', 'in', ACTIVE_RUN_STATUSES),
        ], limit=1)
        if active:
            raise ValidationError(_(
                'Wait for the active NextBot run to finish, or cancel it, '
                'before archiving or deleting this conversation.'
            ))
        return True

    def write(self, values):
        if 'active' in values and not values['active']:
            self._ensure_no_active_runs()
        return super().write(values)

    def unlink(self):
        self._ensure_no_active_runs()
        return super().unlink()

    def _delete_from_workspace(self):
        """Hide the canonical direct chat; hard-delete disposable group chats."""
        self.ensure_one()
        self._ensure_no_active_runs()
        if self.channel_id.channel_type == 'chat':
            self.sudo().write({'active': False})
            return False
        self.sudo().unlink()
        return True

    def _serialize(self):
        self.ensure_one()
        self._ensure_current_user()
        activity_at = iso_utc(self.last_activity_at)
        preview = ''
        if self.last_run_id:
            preview = (self.last_run_id.response_text or self.last_run_id.prompt or '')[:180]
        return {
            'id': self.id,
            'name': self.name,
            'title': self.name,
            'active': self.active,
            'archived': not self.active,
            'channel_id': self.channel_id.id,
            'last_activity_at': activity_at,
            'last_activity': activity_at,
            'updated_at': activity_at,
            'preview': preview,
            'last_run_id': self.last_run_id.id or False,
        }
