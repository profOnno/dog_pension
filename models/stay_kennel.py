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

    def _log_transition(self, old_kennel, new_kennel, reason=None):
        self.ensure_one()
        if not self.dog_id or old_kennel == new_kennel:
            return
        old_label = old_kennel.name if old_kennel else "—"
        new_label = new_kennel.name if new_kennel else "—"
        body = "<b>Kennel change:</b> %s → %s" % (old_label, new_label)
        if self.start_date and self.end_date:
            body += " (%s → %s)" % (
                self.start_date.strftime('%Y-%m-%d %H:%M'),
                self.end_date.strftime('%Y-%m-%d %H:%M'),
            )
        if reason:
            body += "<br/><i>Reason:</i> %s" % reason
        self.dog_id.message_post(body=body, subtype_xmlid='mail.mt_note')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._log_transition(None, rec.kennel_id, rec.notes)
        return records

    def write(self, vals):
        old_data = {}
        if 'kennel_id' in vals:
            for rec in self:
                old_data[rec.id] = rec.kennel_id
        res = super().write(vals)
        if 'kennel_id' in vals:
            for rec in self:
                old = old_data.get(rec.id)
                if old != rec.kennel_id:
                    rec._log_transition(old, rec.kennel_id, rec.notes)
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

    @api.constrains('kennel_id', 'start_date', 'end_date')
    def _check_kennel_state_and_capacity(self):
        for sk in self:
            if not (sk.kennel_id and sk.start_date and sk.end_date):
                continue
            # 1. Kennel must be available
            if sk.kennel_id.state in ('maintenance', 'blocked'):
                raise ValidationError(
                    "Kennel '%s' is in status '%s' and cannot be assigned."
                    % (sk.kennel_id.name, sk.kennel_id.state)
                )
            # 2. Capacity check
            overlapping = self.search([
                ('id', '!=', sk.id),
                ('kennel_id', '=', sk.kennel_id.id),
                ('start_date', '<', sk.end_date),
                ('end_date', '>', sk.start_date),
            ])
            dogs = set(o.stay_id.dog_id.id for o in overlapping if o.stay_id.dog_id)
            if sk.stay_id.dog_id:
                dogs.add(sk.stay_id.dog_id.id)
            if len(dogs) > sk.kennel_id.capacity:
                raise ValidationError(
                    "Kennel '%s' has capacity %d but %d dogs are assigned "
                    "during this period."
                    % (sk.kennel_id.name, sk.kennel_id.capacity, len(dogs))
                )
