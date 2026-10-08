from odoo import api, fields, models


class DogPensionDog(models.Model):
    _name = 'dog.pension.dog'
    _description = 'Dog'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # ------------------------------------------------------------------
    # Basic information
    # ------------------------------------------------------------------

    name = fields.Char(string="Dog Name", required=True, tracking=True)
    owner_id = fields.Many2one(
        'res.partner',
        string="Owner",
        required=True,
        ondelete='cascade',
        domain="[('is_company', '=', False)]",
        tracking=True,
    )
    breed_id = fields.Many2one('dog.pension.breed', string="Breed")
    birth_date = fields.Date(string="Birth Date")
    age = fields.Integer(
        string="Age (years)",
        compute='_compute_age',
        store=True,
    )
    weight = fields.Float(string="Weight (kg)")
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender")
    microchip = fields.Char(string="Microchip")
    is_sterilized = fields.Boolean(string="Sterilized")
    vaccination_date = fields.Date(string="Last Vaccination")
    vet_name = fields.Char(string="Veterinarian Name")
    vet_phone = fields.Char(string="Veterinarian Phone")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index")

    image_1920 = fields.Image(string="Photo", max_width=1920, max_height=1920)
    image_1024 = fields.Image(
        string="Photo 1024",
        related='image_1920',
        max_width=1024, max_height=1024,
        store=True, readonly=True,
    )
    image_512 = fields.Image(
        string="Photo 512",
        related='image_1920',
        max_width=512, max_height=512,
        store=True, readonly=True,
    )
    image_256 = fields.Image(
        string="Photo 256",
        related='image_1920',
        max_width=256, max_height=256,
        store=True, readonly=True,
    )
    image_128 = fields.Image(
        string="Photo 128",
        related='image_1920',
        max_width=128, max_height=128,
        store=True, readonly=True,
    )

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    stay_ids = fields.One2many(
        'dog.pension.stay', 'dog_id', string="Stays"
    )
    stay_count = fields.Integer(
        string="Stays", compute='_compute_stay_count'
    )

    # ------------------------------------------------------------------
    # Current location
    # ------------------------------------------------------------------

    current_kennel_id = fields.Many2one(
        'dog.pension.kennel',
        string="Current Kennel",
        compute='_compute_current_location',
        store=False,
    )
    current_room_id = fields.Many2one(
        'dog.pension.room',
        string="Current Room",
        compute='_compute_current_location',
        store=False,
    )
    current_hallway_id = fields.Many2one(
        'dog.pension.hallway',
        string="Current Hallway",
        compute='_compute_current_location',
        store=False,
    )
    is_boarding = fields.Boolean(
        string="Currently Boarding",
        compute='_compute_current_location',
        store=False,
    )

    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------

    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for dog in self:
            if dog.birth_date:
                dog.age = (today - dog.birth_date).days // 365
            else:
                dog.age = 0

    def _compute_stay_count(self):
        for dog in self:
            dog.stay_count = len(dog.stay_ids)

    @api.depends(
        'stay_ids.state',
        'stay_ids.kennel_assignment_ids.start_date',
        'stay_ids.kennel_assignment_ids.end_date',
        'stay_ids.kennel_assignment_ids.kennel_id',
    )
    def _compute_current_location(self):
        now = fields.Datetime.now()
        for dog in self:
            kennel = False
            if dog.stay_ids:
                current = dog.stay_ids.filtered(
                    lambda s: s.state == 'in_progress'
                ).kennel_assignment_ids.filtered(
                    lambda sk: sk.start_date <= now <= sk.end_date
                )[:1]
                if current:
                    kennel = current.kennel_id
            dog.current_kennel_id = kennel
            dog.current_room_id = kennel.room_id if kennel else False
            dog.current_hallway_id = kennel.hallway_id if kennel else False
            dog.is_boarding = bool(kennel)

    # ------------------------------------------------------------------
    # Name capitalization
    # ------------------------------------------------------------------

    @api.onchange('name')
    def _onchange_name_capitalize(self):
        if self.name:
            self.name = self.name[0].upper() + self.name[1:]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = vals['name'][0].upper() + vals['name'][1:]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals['name'][0].upper() + vals['name'][1:]
        return super().write(vals)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_view_stays(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stays',
            'res_model': 'dog.pension.stay',
            'view_mode': 'list,form',
            'domain': [('dog_id', '=', self.id)],
            'context': {
                'default_dog_id': self.id,
                'default_owner_id': self.owner_id.id,
            },
        }


class DogPensionBreed(models.Model):
    _name = 'dog.pension.breed'
    _description = 'Dog Breed'
    _order = 'name'

    name = fields.Char(string="Breed Name", required=True)
    description = fields.Text(string="Description")
