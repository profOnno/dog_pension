from odoo import api, fields, models
from odoo.exceptions import ValidationError
import base64
from io import BytesIO

import qrcode


class DogPensionKennel(models.Model):
    _name = 'dog.pension.kennel'
    _description = 'Dog Pension Kennel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'hallway_id, sequence, name'

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Label",
        required=True,
        tracking=True,
        help="The label visible on the kennel door, e.g. 'A-01'.",
    )

    qr_code = fields.Binary(
        string="QR Code",
        compute='_compute_qr_code',
        store=True,
    )

    sequence = fields.Integer(
        string="Position",
        default=10,
        help="Order within the hallway, from the entrance.",
    )

    # ------------------------------------------------------------------
    # Location
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Physical characteristics
    # ------------------------------------------------------------------

    size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('xl', 'Extra Large'),
    ], string="Size", default='medium', tracking=True)

    capacity = fields.Integer(
        string="Capacity",
        default=4,
        required=True,
        help="Maximum number of dogs in this kennel at the same time.",
    )
    has_outdoor_access = fields.Boolean(string="Outdoor Access")
    has_heating = fields.Boolean(string="Heated")
    notes = fields.Text(string="Notes")

    # ------------------------------------------------------------------
    # Manual state (set by the user)
    # ------------------------------------------------------------------

    state = fields.Selection([
        ('available', 'Available'),
        ('maintenance', 'Maintenance'),
        ('blocked', 'Blocked'),
    ], string="Status", default='available', tracking=True)

    # ------------------------------------------------------------------
    # Computed occupancy
    # ------------------------------------------------------------------

    current_occupancy = fields.Integer(
        string="Occupancy",
        compute='_compute_occupancy',
        store=True,
    )
    occupancy_state = fields.Selection([
        ('empty', 'Empty'),
        ('partial', 'Partial'),
        ('full', 'Full'),
    ], string="Occupancy", compute='_compute_occupancy', store=True)

    # ------------------------------------------------------------------
    # Company
    # ------------------------------------------------------------------

    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        related='hallway_id.company_id',
        store=True,
    )

    # ------------------------------------------------------------------
    # Current occupant (first dog found in the current period)
    # ------------------------------------------------------------------

    current_dog_ids = fields.Many2many(
        'dog.pension.dog',
        'dog_pension_kennel_current_dog_rel',  # relation table
        'kennel_id',
        'dog_id',
        string="Current Dogs",
        compute='_compute_current_assignment',
        store=True,
    )
    current_dogs_label = fields.Char(
        string="Current Dog(s)",
        compute='_compute_current_assignment',
        store=False,
    )
    current_dogs_html = fields.Html(
        string="Current Dogs",
        compute='_compute_current_assignment',
        store=False,
        sanitize=False,
    )
    current_stay_ids = fields.Many2many(
        'dog.pension.stay',
        'dog_pension_kennel_current_stay_rel',
        'kennel_id',
        'stay_id',
        string="Current Stays",
        compute='_compute_current_assignment',
        store=True,
    )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    stay_kennel_ids = fields.One2many(
        'dog.pension.stay.kennel',
        'kennel_id',
        string="Assignment History",
    )
    stay_kennel_count = fields.Integer(
        string="Assignments",
        compute='_compute_stay_kennel_count',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('name')
    def _compute_qr_code(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for kennel in self:
            if not kennel.id or not base_url:
                kennel.qr_code = False
                continue
            url = "%s/web#id=%d&model=dog.pension.kennel&view_type=form" % (
                base_url, kennel.id
            )
            kennel.qr_code = kennel._generate_qr(url)

    @api.model
    def _generate_qr(self, data, size=4):
        """Generate a QR code PNG and return it as base64."""
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=size,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue())

    @api.depends(
        'stay_kennel_ids.start_date',
        'stay_kennel_ids.end_date',
        'stay_kennel_ids.stay_id',
        'stay_kennel_ids.stay_id.dog_id',
        'stay_kennel_ids.kennel_id',
        'capacity',
    )
    def _compute_occupancy(self):
        now = fields.Datetime.now()
        for kennel in self:
            current = kennel.stay_kennel_ids.filtered(
                lambda sk: sk.start_date <= now <= sk.end_date
            )
            dogs = set(
                sk.stay_id.dog_id.id
                for sk in current
                if sk.stay_id.dog_id
            )
            kennel.current_occupancy = len(dogs)
            if kennel.current_occupancy == 0:
                kennel.occupancy_state = 'empty'
            elif kennel.current_occupancy >= kennel.capacity:
                kennel.occupancy_state = 'full'
            else:
                kennel.occupancy_state = 'partial'

    @api.depends(
        'stay_kennel_ids.start_date',
        'stay_kennel_ids.end_date',
        'stay_kennel_ids.stay_id',
        'stay_kennel_ids.stay_id.dog_id',
    )
    def _compute_current_assignment(self):
        now = fields.Datetime.now()
        for kennel in self:
            current = kennel.stay_kennel_ids.filtered(
                lambda sk: sk.start_date <= now <= sk.end_date
            )
            # Unique dogs (a dog should only appear once)
            dogs = self.env['dog.pension.dog']
            stays = self.env['dog.pension.stay']
            seen_dogs = set()
            seen_stays = set()
            for sk in current:
                if sk.stay_id.dog_id and sk.stay_id.dog_id.id not in seen_dogs:
                    dogs |= sk.stay_id.dog_id
                    seen_dogs.add(sk.stay_id.dog_id.id)
                if sk.stay_id and sk.stay_id.id not in seen_stays:
                    stays |= sk.stay_id
                    seen_stays.add(sk.stay_id.id)
            kennel.current_dog_ids = dogs
            kennel.current_stay_ids = stays
            kennel.current_dogs_label = ", ".join(dogs.mapped('name')) or ""
            kennel.current_dogs_html = " ".join(
                '<a href="/odoo/dog.pension.dog/%s">%s</a>' % (dog.id, dog.name)
                for dog in dogs
            )

    def _compute_stay_kennel_count(self):
        for kennel in self:
            kennel.stay_kennel_count = len(kennel.stay_kennel_ids)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

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

    @api.constrains('capacity')
    def _check_capacity(self):
        for kennel in self:
            if kennel.capacity < 1:
                raise ValidationError(
                    "Capacity must be at least 1."
                )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

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

    def action_set_maintenance(self):
        self.write({'state': 'maintenance'})

    def action_set_available(self):
        self.write({'state': 'available'})

    def action_set_blocked(self):
        self.write({'state': 'blocked'})
