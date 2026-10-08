from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DogPensionStayKennel(models.Model):
    _name = 'dog.pension.stay.kennel'
    _description = 'Kennel Assignment during a Stay'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for sk in self:
            if sk.start_date and sk.end_date:
                delta = sk.end_date - sk.start_date
                sk.duration_days = max(0.0, delta.total_seconds() / 86400.0)
            else:
                sk.duration_days = 0.0

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for sk in self:
            if sk.start_date and sk.end_date and sk.end_date <= sk.start_date:
                raise ValidationError(
                    "The end date of the kennel assignment must be after "
                    "the start date."
                )

    @api.constrains('stay_id', 'kennel_id', 'start_date', 'end_date')
    def _check_no_double_assignment(self):
        """A dog cannot be in two kennels at the same time."""
        for sk in self:
            if not (sk.stay_id and sk.kennel_id and sk.start_date and sk.end_date):
                continue
            # Same dog, any stay, overlapping period
            overlapping = self.search([
                ('id', '!=', sk.id),
                ('stay_id.dog_id', '=', sk.stay_id.dog_id.id),
                ('start_date', '<', sk.end_date),
                ('end_date', '>', sk.start_date),
            ])
            if overlapping:
                other = overlapping[0]
                raise ValidationError(
                    "Dog '%s' is already in kennel '%s' during this period "
                    "(%s → %s). A dog cannot be in two kennels at the same "
                    "time."
                    % (
                        sk.stay_id.dog_id.name,
                        other.kennel_id.name,
                        other.start_date.strftime('%Y-%m-%d %H:%M'),
                        other.end_date.strftime('%Y-%m-%d %H:%M'),
                    )
                )

    @api.constrains('kennel_id', 'start_date', 'end_date')
    def _check_kennel_capacity(self):
        """A kennel cannot host more than its capacity at the same time."""
        for sk in self:
            if not (sk.kennel_id and sk.start_date and sk.end_date):
                continue
            if sk.kennel_id.state in ('maintenance', 'blocked'):
                raise ValidationError(
                    "Kennel '%s' is in status '%s' and cannot be assigned."
                    % (sk.kennel_id.name, sk.kennel_id.state)
                )
            overlapping = self.search([
                ('id', '!=', sk.id),
                ('kennel_id', '=', sk.kennel_id.id),
                ('start_date', '<', sk.end_date),
                ('end_date', '>', sk.start_date),
            ])
            dogs = set()
            for o in overlapping:
                if o.stay_id.dog_id:
                    dogs.add(o.stay_id.dog_id.id)
            if sk.stay_id.dog_id:
                dogs.add(sk.stay_id.dog_id.id)
            if len(dogs) > sk.kennel_id.capacity:
                raise ValidationError(
                    "Kennel '%s' has capacity %d, but %d dogs would be "
                    "assigned during this period."
                    % (sk.kennel_id.name, sk.kennel_id.capacity, len(dogs))
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

    # ------------------------------------------------------------------
    # Chatter logging
    # ------------------------------------------------------------------

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


    # ------------------------------------------------------------------
    # Create — close overlapping assignment in the same stay BEFORE
    # validation, so a move is not blocked.
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            stay_id = vals.get('stay_id')
            kennel_id = vals.get('kennel_id')
            start_date = vals.get('start_date')
            end_date = vals.get('end_date')

            if not (stay_id and kennel_id and start_date and end_date):
                continue

            stay = self.env['dog.pension.stay'].browse(stay_id)
            kennel = self.env['dog.pension.kennel'].browse(kennel_id)

            # 1. Kennel must be available
            if kennel.state in ('maintenance', 'blocked'):
                raise ValidationError(
                    "Kennel '%s' is in status '%s' and cannot be assigned."
                    % (kennel.name, kennel.state)
                )

            # 2. FIRST: close any overlapping assignment in the SAME stay
            #    This must happen BEFORE validation, so a move is not blocked.
            overlapping_same_stay = self.search([
                ('stay_id', '=', stay_id),
                ('start_date', '<', start_date),
                ('end_date', '>', start_date),
            ])
            for old in overlapping_same_stay:
                old.end_date = start_date

            # 3. THEN: validate against OTHER stays (not the same one)
            dog_overlap_other_stay = self.search([
                ('stay_id.dog_id', '=', stay.dog_id.id),
                ('stay_id', '!=', stay_id),
                ('start_date', '<', end_date),
                ('end_date', '>', start_date),
            ])
            if dog_overlap_other_stay:
                other = dog_overlap_other_stay[0]
                raise ValidationError(
                    "Dog '%s' is already in kennel '%s' during this period "
                    "(%s → %s). A dog cannot be in two kennels at the same "
                    "time."
                    % (
                        stay.dog_id.name,
                        other.kennel_id.name,
                        other.start_date.strftime('%Y-%m-%d %H:%M'),
                        other.end_date.strftime('%Y-%m-%d %H:%M'),
                    )
                )

            # 4. Capacity check (excluding the same stay)
            kennel_overlap = self.search([
                ('kennel_id', '=', kennel.id),
                ('stay_id', '!=', stay_id),
                ('start_date', '<', end_date),
                ('end_date', '>', start_date),
            ])
            dogs = set()
            for o in kennel_overlap:
                if o.stay_id.dog_id:
                    dogs.add(o.stay_id.dog_id.id)
            if stay.dog_id:
                dogs.add(stay.dog_id.id)
            if len(dogs) > kennel.capacity:
                raise ValidationError(
                    "Kennel '%s' has capacity %d, but %d dogs would be "
                    "assigned during this period."
                    % (kennel.name, kennel.capacity, len(dogs))
                )

        # 5. Create the new records
        records = super().create(vals_list)

        # 6. Log the transitions on the dog's chatter
        for rec in records:
            previous = self.search([
                ('stay_id', '=', rec.stay_id.id),
                ('end_date', '=', rec.start_date),
                ('id', '!=', rec.id),
            ], limit=1, order='end_date desc')
            if previous:
                rec._log_transition(
                    old_kennel=previous.kennel_id,
                    new_kennel=rec.kennel_id,
                    reason=rec.notes,
                )
            else:
                rec._log_transition(
                    old_kennel=None,
                    new_kennel=rec.kennel_id,
                    reason=rec.notes,
                )

        return records

    # ------------------------------------------------------------------
    # Write — log kennel changes on the dog's chatter
    # ------------------------------------------------------------------

    def write(self, vals):
        # Capture old kennel_id before the write
        old_data = {}
        if 'kennel_id' in vals:
            for rec in self:
                old_data[rec.id] = rec.kennel_id

        res = super().write(vals)

        # Log kennel changes on the dog's chatter
        if 'kennel_id' in vals:
            for rec in self:
                old = old_data.get(rec.id)
                if old != rec.kennel_id:
                    rec._log_transition(
                        old_kennel=old,
                        new_kennel=rec.kennel_id,
                        reason=vals.get('notes') or rec.notes,
                    )
        return res

    # ------------------------------------------------------------------
    # Unlink — log removal
    # ------------------------------------------------------------------

    def unlink(self):
        for rec in self:
            if rec.dog_id:
                rec.dog_id.message_post(
                    body=(
                        "<b>Kennel assignment removed:</b> %s "
                        "(was %s → %s)"
                        % (
                            rec.kennel_id.name,
                            rec.start_date.strftime('%Y-%m-%d %H:%M')
                            if rec.start_date else '?',
                            rec.end_date.strftime('%Y-%m-%d %H:%M')
                            if rec.end_date else '?',
                        )
                    ),
                    subtype_xmlid='mail.mt_note',
                )
        return super().unlink()
