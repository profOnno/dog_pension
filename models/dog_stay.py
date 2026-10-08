from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DogPensionStay(models.Model):
    _name = 'dog.pension.stay'
    _description = 'Dog Stay at Pension'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    dog_id = fields.Many2one(
        'dog.pension.dog',
        string="Dog",
        required=True,
        ondelete='cascade',
    )
    owner_id = fields.Many2one(
        'res.partner',
        string="Owner",
        related='dog_id.owner_id',
        store=True,
        readonly=True,
    )
    start_date = fields.Datetime(string="Check-in", required=True, tracking=True)
    end_date = fields.Datetime(string="Check-out", required=True, tracking=True)
    duration_days = fields.Float(
        string="Duration (days)",
        compute='_compute_duration',
        store=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='draft', tracking=True)

    sale_order_id = fields.Many2one(
        'sale.order',
        string="Sales Order",
        ondelete='cascade',
        readonly=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string="Sales Order Line",
        ondelete='set null',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
    )
    notes = fields.Text(string="Notes")
    special_needs = fields.Text(string="Special Needs / Dietary Requirements")
    food_provided = fields.Boolean(string="Owner Provides Food", default=True)
    medication = fields.Text(string="Medication")

    kennel_assignment_ids = fields.One2many(
        'dog.pension.stay.kennel',
        'stay_id',
        string="Kennel Assignments",
    )
    kennel_assignment_count = fields.Integer(
        string="Kennel Assignments",
        compute='_compute_kennel_assignment_count',
    )
    current_kennel_id = fields.Many2one(
        'dog.pension.kennel',
        string="Current Kennel",
        compute='_compute_current_kennel',
        store=False,
    )
    room_id = fields.Many2one(
        'dog.pension.room',
        string="Current Room",
        compute='_compute_current_kennel',
        store=False,
    )
    hallway_id = fields.Many2one(
        'dog.pension.hallway',
        string="Current Hallway",
        compute='_compute_current_kennel',
        store=False,
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends(
        'kennel_assignment_ids.start_date',
        'kennel_assignment_ids.end_date',
        'kennel_assignment_ids.kennel_id',
        'kennel_assignment_ids.kennel_id.room_id',
        'kennel_assignment_ids.kennel_id.hallway_id',
    )

    def _compute_current_kennel(self):
        now = fields.Datetime.now()
        for stay in self:
            kennel = False
            if stay.kennel_assignment_ids:
                current = stay.kennel_assignment_ids.filtered(
                    lambda sk: sk.start_date <= now <= sk.end_date
                )[:1]
                if current:
                    kennel = current.kennel_id
            stay.current_kennel_id = kennel
            stay.room_id = kennel.room_id if kennel else False
            stay.hallway_id = kennel.hallway_id if kennel else False

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for stay in self:
            if stay.start_date and stay.end_date:
                delta = stay.end_date - stay.start_date
                stay.duration_days = max(0.0, delta.total_seconds() / 86400.0)
            else:
                stay.duration_days = 0.0

    def _compute_kennel_assignment_count(self):
        for stay in self:
            stay.kennel_assignment_count = len(stay.kennel_assignment_ids)

    def write(self, vals):
        res = super().write(vals)
        if 'end_date' in vals:
            for stay in self:
                last_assignment = stay.kennel_assignment_ids.sorted(
                    key=lambda sk: sk.start_date, reverse=True
                )[:1]
                if last_assignment and stay.end_date:
                    last_assignment.end_date = stay.end_date
        return res

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for stay in self:
            if stay.start_date and stay.end_date and stay.end_date <= stay.start_date:
                raise ValidationError("Check-out date must be after Check-in date.")

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                sequence = self.env['ir.sequence'].next_by_code('dog.pension.stay')
                if not sequence:
                    raise ValidationError(
                        "The sequence 'dog.pension.stay' is not configured. "
                        "Please contact your administrator."
                    )
                vals['name'] = sequence
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_start(self):
        self.write({'state': 'in_progress'})
        for stay in self:
            kennel = stay.current_kennel_id
            location = kennel.name if kennel else "no kennel assigned yet"
            stay.dog_id.message_post(
                body=(
                    "<b>Checked in</b> at the pension. "
                    "Current location: %s" % location
                ),
                subtype_xmlid='mail.mt_note',
            )

    def action_done(self):
        self.write({'state': 'done'})
        for stay in self:
            if stay.sale_order_line_id:
                stay.sale_order_line_id.qty_delivered = (
                    stay.sale_order_line_id.product_uom_qty
                )
            stay.dog_id.message_post(
                body="<b>Checked out</b> — stay finished.",
                subtype_xmlid='mail.mt_note',
            )

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def action_view_kennel_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kennel Assignments',
            'res_model': 'dog.pension.stay.kennel',
            'view_mode': 'list,form',
            'domain': [('stay_id', '=', self.id)],
            'context': {
                'default_stay_id': self.id,
            },
        }

    def action_extend_stay(self):
        """Open a wizard to extend the stay."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Extend Stay',
            'res_model': 'dog.pension.stay.extend',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_stay_id': self.id,
            },
        }
