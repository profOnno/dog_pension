from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DogPensionStayKennel(models.Model):
    _name = 'dog.pension.stay.kennel'
    _description = 'Kennel Assignment during a Stay'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    stay_id = fields.Many2one(
        'dog.pension.stay',
        string="Stay",
        required=True,
        ondelete='cascade',
    )
    kennel_id = fields.Many2one(
        'dog.pension.kennel',
        string="Kennel",
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    start_date = fields.Datetime(
        string="From",
        required=True,
        tracking=True,
    )
    end_date = fields.Datetime(
        string="To",
        required=True,
        tracking=True,
    )
    duration_days = fields.Float(
        string="Duration (days)",
        compute='_compute_duration',
        store=True,
    )
    notes = fields.Text(string="Reason for Change")
    company_id = fields.Many2one(
        'res.company',
        related='stay_id.company_id',
        store=True,
    )

    # Related for convenience
    dog_id = fields.Many2one(
        'dog.pension.dog',
        string="Dog",
        related='stay_id.dog_id',
        store=True,
        readonly=True,
    )
    room_id = fields.Many2one(
        'dog.pension.room',
        string="Room",
        related='kennel_id.room_id',
        store=True,
        readonly=True,
    )
    hallway_id = fields.Many2one(
        'dog.pension.hallway',
        string="Hallway",
        related='kennel_id.hallway_id',
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Close any assignment that overlaps the start of the new one
            overlapping = self.search([
                ('id', '!=', rec.id),
                ('stay_id', '=', rec.stay_id.id),
                ('start_date', '<', rec.start_date),
                ('end_date', '>', rec.start_date),
            ])
            for old in overlapping:
                old.end_date = rec.start_date
            # Log the transition on the dog's chatter
            rec._log_transition(
                old_kennel=overlapping[:1].kennel_id,
                new_kennel=rec.kennel_id,
                reason=rec.notes,
            )
        return records
    @api.model
    def default_get(self, fields_list):
        """Prefill dates when creating a new kennel assignment.

        - start_date: now
        - end_date: the end_date of the related stay
        """
        res = super().default_get(fields_list)
        stay_id = self.env.context.get('default_stay_id')
        if stay_id:
            stay = self.env['dog.pension.stay'].browse(stay_id)
            res['start_date'] = fields.Datetime.now()
            if stay.end_date:
                res['end_date'] = stay.end_date
        return res

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for sk in self:
            if sk.start_date and sk.end_date:
                delta = sk.end_date - sk.start_date
                sk.duration_days = max(0.0, delta.total_seconds() / 86400.0)
            else:
                sk.duration_days = 0.0

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for sk in self:
            if sk.start_date and sk.end_date and sk.end_date <= sk.start_date:
                raise ValidationError(
                    "The end date of the kennel assignment must be after "
                    "the start date."
                )

    @api.constrains('kennel_id', 'start_date', 'end_date')
    def _check_kennel_availability(self):
        for sk in self:
            overlapping = self.search([
                ('id', '!=', sk.id),
                ('kennel_id', '=', sk.kennel_id.id),
                ('start_date', '<', sk.end_date),
                ('end_date', '>', sk.start_date),
            ])
            if overlapping:
                raise ValidationError(
                    "Kennel '%s' is already assigned during this period "
                    "(conflicting assignment for dog '%s')."
                    % (sk.kennel_id.name, overlapping[0].dog_id.name or '?')
                )

    @api.constrains('stay_id', 'start_date', 'end_date')
    def _check_within_stay(self):
        for sk in self:
            stay = sk.stay_id
            if not stay.start_date or not stay.end_date:
                continue
            if sk.start_date < stay.start_date:
                raise ValidationError(
                    "The assignment cannot start before the stay begins."
                )
            if sk.end_date > stay.end_date:
                raise ValidationError(
                    "The assignment cannot end after the stay ends."
                )
