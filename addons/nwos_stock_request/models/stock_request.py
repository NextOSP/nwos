# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from nwos import _, api, fields, models
from nwos.exceptions import UserError


class StockRequest(models.Model):
    _name = 'stock.request'
    _description = 'Stock Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'))
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    requester_id = fields.Many2one(
        'res.users', string='Requester', required=True, tracking=True,
        default=lambda self: self.env.user)
    request_date = fields.Date(
        string='Request Date', default=fields.Date.context_today, tracking=True)
    date_required = fields.Date(string='Required By', tracking=True)
    purpose = fields.Selection([
        ('stock', 'Replenish Stock'),
        ('office', 'Office / Consumable'),
        ('project', 'Project'),
        ('manufacture', 'Manufacturing'),
    ], string='Purpose', default='stock', required=True, tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', tracking=True,
        default=lambda self: self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1))
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account')
    note = fields.Text(string='Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('done', 'Purchased'),
        ('refused', 'Refused'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False, index=True)

    department_id = fields.Many2one(
        'hr.department', string='Department', tracking=True,
        compute='_compute_department_id', store=True, readonly=False)

    approver_id = fields.Many2one(
        'res.users', string='Approved By', readonly=True, copy=False, tracking=True)
    approved_date = fields.Datetime(string='Approved On', readonly=True, copy=False)
    refuse_reason = fields.Text(string='Refusal Reason', readonly=True, copy=False)

    awaiting_my_approval = fields.Boolean(
        compute='_compute_awaiting_my_approval',
        search='_search_awaiting_my_approval',
        help="Technical: this request has an approval step waiting for me.")

    line_ids = fields.One2many(
        'stock.request.line', 'request_id', string='Items', copy=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id,
        help="Currency of the estimated amounts on this request.")
    estimated_total = fields.Monetary(
        string='Estimated Total', compute='_compute_estimated_total', store=True)

    purchase_order_ids = fields.One2many(
        'purchase.order', 'stock_request_id', string='Purchase Orders')
    purchase_order_count = fields.Integer(compute='_compute_purchase_orders')
    picking_ids = fields.Many2many(
        'stock.picking', string='Receipts', compute='_compute_pickings')
    picking_count = fields.Integer(compute='_compute_pickings')
    stock_reference_id = fields.Many2one(
        'stock.reference', string='Stock Reference', copy=False, readonly=True,
        help="Ties the moves created by the Replenish lines back to this request.")
    pending_source_count = fields.Integer(
        string='Lines To Source', compute='_compute_pending_source_count',
        help="Technical: items that still have to be purchased or replenished.")

    # Downstream purchase lifecycle (from the linked POs / receipts / bills)
    fulfillment_state = fields.Selection([
        ('rfq', 'RFQ'),
        ('ordered', 'Ordered'),
        ('waiting', 'Waiting Delivery'),
        ('received', 'Received'),
    ], string='Delivery Progress', compute='_compute_fulfillment')
    payment_state = fields.Selection([
        ('no_bill', 'No Bill'),
        ('to_pay', 'To Pay'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], string='Payment', compute='_compute_fulfillment')

    @api.depends('line_ids.price_subtotal')
    def _compute_estimated_total(self):
        for request in self:
            request.estimated_total = sum(request.line_ids.mapped('price_subtotal'))

    @api.depends('requester_id')
    def _compute_department_id(self):
        for request in self:
            request.department_id = request.requester_id.employee_id.department_id

    @api.depends_context('uid')
    def _compute_awaiting_my_approval(self):
        waiting = set(self.env['approval.request'].search([
            ('res_model', '=', 'stock.request'),
            ('res_id', 'in', self.ids),
            ('state', '=', 'pending'),
            ('pending_approver_ids', 'in', self.env.uid),
        ]).mapped('res_id'))
        for request in self:
            request.awaiting_my_approval = request.id in waiting

    def _search_awaiting_my_approval(self, operator, value):
        ids = self.env['approval.request'].search([
            ('res_model', '=', 'stock.request'),
            ('state', '=', 'pending'),
            ('pending_approver_ids', 'in', self.env.uid),
        ]).mapped('res_id')
        positive = (operator == '=') == bool(value)
        return [('id', 'in' if positive else 'not in', ids)]

    @api.depends('purchase_order_ids')
    def _compute_purchase_orders(self):
        for request in self:
            request.purchase_order_count = len(request.purchase_order_ids)

    @api.depends('line_ids.product_qty', 'line_ids.is_sourced')
    def _compute_pending_source_count(self):
        for request in self:
            request.pending_source_count = len(request._lines_to_source())

    @api.depends('purchase_order_ids.picking_ids',
                 'stock_reference_id.move_ids.picking_id')
    def _compute_pickings(self):
        for request in self:
            pickings = request.purchase_order_ids.picking_ids \
                | request.stock_reference_id.picking_ids
            request.picking_ids = pickings
            request.picking_count = len(pickings)

    @api.depends('purchase_order_ids.state', 'purchase_order_ids.receipt_status',
                 'purchase_order_ids.invoice_ids.payment_state',
                 'purchase_order_ids.picking_ids.state',
                 'stock_reference_id.move_ids.picking_id.state')
    def _compute_fulfillment(self):
        for request in self:
            pos = request.purchase_order_ids
            confirmed = pos.filtered(lambda p: p.state == 'purchase')
            # --- delivery progress ---
            if not pos:
                # Replenish-only request: follow the moves it launched instead.
                pickings = request.picking_ids
                if not pickings:
                    request.fulfillment_state = False
                elif all(pk.state in ('done', 'cancel') for pk in pickings):
                    request.fulfillment_state = 'received'
                else:
                    request.fulfillment_state = 'waiting'
            elif not confirmed:
                request.fulfillment_state = 'rfq'
            elif all(p.receipt_status == 'full' for p in confirmed):
                request.fulfillment_state = 'received'
            elif any(p.receipt_status == 'partial' for p in confirmed) or \
                    request.picking_ids.filtered(
                        lambda pk: pk.state not in ('done', 'cancel')):
                request.fulfillment_state = 'waiting'
            else:
                request.fulfillment_state = 'ordered'
            # --- payment ---
            bills = pos.invoice_ids.filtered(lambda m: m.state != 'cancel')
            if not bills:
                request.payment_state = 'no_bill'
            elif all(b.payment_state in ('paid', 'in_payment', 'reversed')
                     for b in bills):
                request.payment_state = 'paid'
            elif any(b.payment_state in ('paid', 'in_payment', 'partial')
                     for b in bills):
                request.payment_state = 'partial'
            else:
                request.payment_state = 'to_pay'

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq_date = vals.get('request_date')
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'stock.request', sequence_date=seq_date) or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Approval engine
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Workflow
    #
    # Approval itself lives in `nwos_approval`: a rule on stock.request gates
    # `action_confirm_request`, which the framework re-runs once every step is
    # approved. This model only owns its own state.
    # ------------------------------------------------------------------
    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError(_("Add at least one item before submitting."))
            request.state = 'to_approve'
        return self.action_confirm_request()

    def action_confirm_request(self):
        """Move an approved request to 'approved'. Gated by nwos_approval."""
        self.write({
            'state': 'approved',
            'approver_id': self.env.uid,
            'approved_date': fields.Datetime.now(),
        })
        self.activity_feedback(['mail.mail_activity_data_todo'])
        for request in self:
            request._notify_buyers()
        return True

    def action_approve(self):
        """Approve the current step of the pending approval request."""
        Request = self.env['approval.request']
        for request in self:
            if request.state != 'to_approve':
                raise UserError(_("Only submitted requests can be approved."))
            approval = Request.search([
                ('res_model', '=', 'stock.request'),
                ('res_id', '=', request.id),
                ('state', '=', 'pending'),
            ], limit=1)
            if not approval:
                raise UserError(_("There is no pending step to approve."))
            approval.approval_action_approve()
        return True

    def action_refuse_from_approval(self):
        """Called by nwos_approval when an approval is refused."""
        self.write({
            'state': 'refused',
            'refuse_reason': self.env.context.get('approval_reject_reason'),
        })
        return True

    def _notify_buyers(self):
        """Ping the purchasing team that an approved request is ready to source."""
        self.ensure_one()
        template = self.env.ref(
            'nwos_stock_request.mail_template_stock_request_approved',
            raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=False)

    def action_refuse(self):
        return {
            'name': _('Refuse Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.request.refuse',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_cancel(self):
        self.filtered(lambda r: r.state != 'done').write({'state': 'cancel'})
        self.env['approval.request']._cancel_for(self)
        self.activity_feedback(['mail.mail_activity_data_todo'])
        return True

    def action_reset_to_draft(self):
        self.env['approval.request']._cancel_for(self)
        self.write({'state': 'draft', 'approver_id': False, 'approved_date': False,
                    'refuse_reason': False})
        return True

    # ------------------------------------------------------------------
    # Purchase / Replenishment generation (buyer-triggered)
    # ------------------------------------------------------------------
    def _lines_to_source(self):
        """Lines that still have to be turned into a PO or a procurement."""
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.product_qty > 0 and not l.is_sourced)

    def _get_stock_reference(self):
        """The stock.reference tying replenishment moves back to this request."""
        self.ensure_one()
        if not self.stock_reference_id:
            self.stock_reference_id = self.env['stock.reference'].create({
                'name': self.name,
            })
        return self.stock_reference_id

    def action_generate_purchase(self):
        """Buyer action.

        * Purchase lines  -> a real draft RFQ/PO per vendor, linked back here.
        * Replenish lines -> procurement through the product's own routes, tied
          to this request by a stock reference so the resulting receipts /
          manufacturing orders stay visible from here.

        A Purchase line needs a vendor (you cannot raise a PO without one);
        lines missing a vendor are reported so nothing is silently skipped.
        Lines already sourced are skipped, so clicking twice never duplicates.
        """
        self.ensure_one()
        if self.state not in ('approved', 'done'):
            raise UserError(_("Only approved requests can be purchased."))

        active = self._lines_to_source()
        if not active:
            raise UserError(_(
                "Everything on this request has already been sourced."))

        spec_only = active.filtered(lambda l: not l.product_id)
        if spec_only:
            raise UserError(_(
                "These lines have no product yet — create the product from the "
                "specification first:\n%s",
                "\n".join('- %s' % (l.name or '') for l in spec_only)))

        buy_lines = active.filtered(lambda l: l.source_action == 'buy')
        replenish_lines = active.filtered(lambda l: l.source_action == 'replenish')

        missing_vendor = buy_lines.filtered(lambda l: not l._effective_vendor())
        if missing_vendor:
            raise UserError(_(
                "Set a Preferred Vendor on these Purchase lines (or switch their "
                "Source to Replenish):\n%s",
                "\n".join('- %s' % (l.name or '') for l in missing_vendor)))

        # 1) One draft PO per vendor for the Purchase lines, linked to the request
        by_vendor = defaultdict(lambda: self.env['stock.request.line'])
        for line in buy_lines:
            by_vendor[line._effective_vendor()] |= line
        new_orders = self.env['purchase.order']
        for vendor, lines in by_vendor.items():
            new_orders |= self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'origin': self.name,
                'stock_request_id': self.id,
                'order_line': [(0, 0, line._prepare_po_line_vals()) for line in lines],
            })

        # 2) Replenish lines go through their product routes
        if replenish_lines:
            reference = self._get_stock_reference()
            Procurement = self.env['stock.rule'].Procurement
            procurements = [Procurement(
                line.product_id,
                line.product_qty,
                line.product_uom or line.product_id.uom_id,
                self.warehouse_id.lot_stock_id,
                self.name,
                self.name,
                self.company_id,
                line._prepare_procurement_values(route=line.route_id),
            ) for line in replenish_lines]
            self.env['stock.rule'].run(procurements)
            # A Buy route turns the procurement into a PO: adopt it as well so
            # the request keeps a single view of everything it triggered.
            adopted = self.env['purchase.order'].search([
                ('reference_ids', 'in', reference.ids),
                ('stock_request_id', '=', False),
            ])
            adopted.stock_request_id = self.id
            new_orders |= adopted

        active.is_sourced = True
        self.state = 'done'
        self._post_sourcing_summary(new_orders, replenish_lines)
        if new_orders:
            return self.action_view_purchase_orders()
        if self.picking_ids:
            return self.action_view_pickings()
        return self._notify_replenishment_launched()

    def _post_sourcing_summary(self, orders, replenish_lines):
        """Log what the click actually produced — POs and/or replenishments."""
        self.ensure_one()
        parts = []
        if orders:
            parts.append(_("Purchase orders: %s",
                           ", ".join(orders.mapped('name'))))
        if replenish_lines:
            parts.append(_("Replenished through product routes:\n%s", "\n".join(
                '- %s (%s %s)' % (line.name or line.product_id.display_name,
                                  line.product_qty,
                                  (line.product_uom or line.product_id.uom_id).name)
                for line in replenish_lines)))
        if self.picking_ids:
            parts.append(_("Transfers: %s",
                           ", ".join(self.picking_ids.mapped('name'))))
        if parts:
            self.message_post(body="<br/>".join(parts))

    def _notify_replenishment_launched(self):
        """Replenishment produced no document to open (e.g. served from stock)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Replenishment launched"),
                'message': _(
                    "The request was sourced through the product routes. "
                    "No purchase order was needed."),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        orders = self.purchase_order_ids
        action = {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'context': {'create': False},
        }
        if len(orders) == 1:
            action.update(view_mode='form', res_id=orders.id)
        else:
            action.update(view_mode='list,form',
                          domain=[('id', 'in', orders.ids)])
        return action

    @api.model
    def retrieve_dashboard(self):
        """Aggregate counts for the Stock Requests list banner."""
        states = ['draft', 'to_approve', 'approved', 'done']
        base = [('company_id', 'in', self.env.companies.ids)]
        my = base + [('requester_id', '=', self.env.uid)]
        result = {'global': {}, 'my': {}}
        for state in states:
            result['global'][state] = self.search_count(
                base + [('state', '=', state)])
            result['my'][state] = self.search_count(
                my + [('state', '=', state)])
        # requests awaiting the current user's approval (current step)
        awaiting = self.env['approval.request']._awaiting_count(
            res_model='stock.request')
        result['my']['awaiting'] = awaiting
        result['global']['awaiting'] = awaiting
        return result

    def action_view_pickings(self):
        self.ensure_one()
        pickings = self.picking_ids
        action = {
            'name': _('Receipts'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'context': {'create': False},
        }
        if len(pickings) == 1:
            action.update(view_mode='form', res_id=pickings.id)
        else:
            action.update(view_mode='list,form',
                          domain=[('id', 'in', pickings.ids)])
        return action


class StockRequestLine(models.Model):
    _name = 'stock.request.line'
    _description = 'Stock Request Line'
    _rec_name = 'name'

    request_id = fields.Many2one(
        'stock.request', string='Request', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='request_id.company_id', store=True, index=True)
    state = fields.Selection(related='request_id.state', store=True, index=True)

    product_id = fields.Many2one(
        'product.product', string='Product',
        domain="[('purchase_ok', '=', True)]")
    name = fields.Char(string='Description / Specification', required=True)
    product_qty = fields.Float(
        string='Quantity', default=1.0, required=True,
        digits='Product Unit of Measure')
    product_uom = fields.Many2one(
        'uom.uom', string='Unit',
        compute='_compute_product_uom', store=True, readonly=False, precompute=True,
        domain="[('id', 'in', allowed_uom_ids)]")
    allowed_uom_ids = fields.Many2many(
        'uom.uom', compute='_compute_allowed_uom_ids')
    source_action = fields.Selection([
        ('buy', 'Purchase'),
        ('replenish', 'Replenish'),
    ], string='Source', default='buy', required=True,
        help="Purchase: always create an RFQ / Purchase Order.\n"
             "Replenish: use the product's own routes (manufacture, internal "
             "transfer, buy...).")
    vendor_id = fields.Many2one(
        'res.partner', string='Preferred Vendor',
        domain="[('is_company', '=', True)]")
    price_unit = fields.Float(
        string='Est. Unit Price', digits='Product Price')
    price_subtotal = fields.Monetary(
        string='Est. Subtotal', compute='_compute_price_subtotal', store=True)
    currency_id = fields.Many2one(
        related='request_id.currency_id', readonly=True)
    is_sourced = fields.Boolean(
        string='Sourced', readonly=True, copy=False,
        help="This item has already been turned into a purchase order or a "
             "replenishment; it is skipped by Generate Purchase.")
    route_id = fields.Many2one(
        'stock.route', string='Route',
        domain="[('product_selectable', '=', True)]",
        help="Force a specific route (Buy / Manufacture / Transfer). "
             "Leave empty to use the product's own routes.")

    @api.depends('product_qty', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit

    @api.depends('product_id')
    def _compute_allowed_uom_ids(self):
        for line in self:
            line.allowed_uom_ids = line.product_id.uom_id | line.product_id.uom_ids

    @api.depends('product_id')
    def _compute_product_uom(self):
        for line in self:
            if line.product_id and line.product_uom not in line.allowed_uom_ids:
                line.product_uom = line.product_id.uom_id

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if not self.name or self.name == '/':
                self.name = self.product_id.display_name
            seller = self.product_id._select_seller(quantity=self.product_qty)
            if seller:
                self.vendor_id = seller.partner_id
                self.price_unit = seller.price

    def _effective_vendor(self):
        """Vendor to source from: explicit preferred vendor or a product seller."""
        self.ensure_one()
        return self.vendor_id or self.product_id.seller_ids[:1].partner_id

    def _prepare_procurement_values(self, route=False):
        self.ensure_one()
        return {
            'company_id': self.company_id,
            'warehouse_id': self.request_id.warehouse_id,
            'route_ids': route or self.route_id,
            'date_planned': self.request_id.date_required or fields.Datetime.now(),
            'reference_ids': self.request_id._get_stock_reference(),
        }

    def _prepare_po_line_vals(self):
        """Values for the purchase.order.line created from this request line."""
        self.ensure_one()
        return {
            'product_id': self.product_id.id,
            'name': self.name or self.product_id.display_name,
            'product_qty': self.product_qty,
            'product_uom_id': (self.product_uom or self.product_id.uom_id).id,
            'price_unit': self.price_unit,
            'date_planned': fields.Datetime.now(),
        }

    def action_create_product(self):
        """Create a storable/consumable product from the line specification and
        link it back to the line."""
        self.ensure_one()
        if self.product_id:
            raise UserError(_("This line already has a product."))
        uom = self.product_uom or self.env.ref('uom.product_uom_unit')
        product = self.env['product.product'].create({
            'name': self.name,
            'type': 'consu',
            'purchase_ok': True,
            'uom_id': uom.id,
        })
        self.product_id = product
        return {
            'name': _('Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': product.id,
            'view_mode': 'form',
            'target': 'new',
        }


class StockRequestRefuse(models.TransientModel):
    _name = 'stock.request.refuse'
    _description = 'Refuse Stock Request'

    request_id = fields.Many2one('stock.request', required=True)
    reason = fields.Text(string='Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.env['approval.request']._cancel_for(self.request_id)
        self.request_id.write({
            'state': 'refused',
            'refuse_reason': self.reason,
        })
        self.request_id.activity_feedback(['mail.mail_activity_data_todo'])
        self.request_id.message_post(
            body=_("Request refused: %s", self.reason))
        return {'type': 'ir.actions.act_window_close'}
