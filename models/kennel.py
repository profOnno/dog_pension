from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DogPensionKennel(models.Model):
    _name = 'dog.pension.kennel'
    _description = 'Dog Pension Kennel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'hallway_id, sequence, name'

    name = fields.Char(
        string="Label",
        required=True,
        tracking=True,
        help="The label visible on the kennel door, e.g. 'A-01'.",
    )
    sequence = fields.Integer(
        string="Position",
        default=10,
        help="Order within the hallway, from the entrance.",
    )
    hallway_id = fields.Many2one(
        'dog.pension.hallway',
        string="Hallway",
        required=True,
        ondelete='cascade',
    )
    room_id = fields.Many2one(
        'dog.pension.room',
        string="Room",
        related='hallway_id.room_id',
        store=True,
        readonly=True,
    )

    size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('xl', 'Extra Large'),
    ], string="Size", default='medium', tracking=True)
    has_outdoor_access = fields.Boolean(string="Outdoor Access")
    has_heating = fields.Boolean(string="Heated")
    notes = fields.Text(string="Notes")

    state = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance'),
        ('blocked', 'Blocked'),
    ], string="Status", default='available', tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        related='hallway_id.company_id',
        store=True,
    )

    # Current occupant
    current_stay_kennel_id = fields.Many2one(
        'dog.pension.stay.kennel',
        string="Current Assignment",
        compute='_compute_current_assignment',
    )
    current_stay_id = fields.Many2one(
        'dog.pension.stay',
        string="Current Stay",
        compute='_compute_current_assignment',
        store=False,
    )
    current_dog_id = fields.Many2one(
        'dog.pension.dog',
        string="Current Dog",
        compute='_compute_current_assignment',
        store=False,
    )

    # History — all assignments ever made to this kennel
    stay_kennel_ids = fields.One2many(
        'dog.pension.stay.kennel', 'kennel_id', string="Assignment History"
    )
    stay_kennel_count = fields.Integer(
        string="Assignments", compute='_compute_stay_kennel_count'
    )

    @api.depends(
        'stay_kennel_ids.start_date',
        'stay_kennel_ids.end_date',
        'stay_kennel_ids.stay_id',
        'stay_kennel_ids.kennel_id',
    )
    def _compute_current_assignment(self):
        now = fields.Datetime.now()
        for kennel in self:
            current = kennel.stay_kennel_ids.filtered(
                lambda sk: sk.start_date <= now <= sk.end_date
            )[:1]
            kennel.current_stay_kennel_id = current
            kennel.current_stay_id = current.stay_id
            kennel.current_dog_id = current.stay_id.dog_id

    def _compute_stay_kennel_count(self):
        for kennel in self:
            kennel.stay_kennel_count = len(kennel.stay_kennel_ids)

    @api.constrains('name', 'hallway_id')
    def _check_unique_label(self):
        for kennel in self:
            duplicate = self.search([
                ('id', '!=', kennel.id),
                ('name', '=', kennel.name),
                ('hallway_id', '=', kennel.hallway_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "A kennel with label '%s' already exists in hallway '%s'."
                    % (kennel.name, kennel.hallway_id.name)
                )

    def action_view_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assignments',
            'res_model': 'dog.pension.stay.kennel',
            'view_mode': 'list,form',
            'domain': [('kennel_id', '=', self.id)],
            'context': {'default_kennel_id': self.id},
        }
