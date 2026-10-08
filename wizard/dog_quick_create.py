from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DogQuickCreate(models.TransientModel):
    _name = 'dog.pension.dog.quick.create'
    _description = 'Quick Create Dog from Sale Order Line'

    # Context comes from the sale.order.line button
    line_id = fields.Many2one(
        'sale.order.line',
        string="Sale Order Line",
        required=True,
        ondelete='cascade',
    )
    owner_id = fields.Many2one(
        'res.partner',
        string="Owner",
        required=True,
    )

    # Fields the user fills in
    name = fields.Char(string="Dog Name", required=True)
    breed_id = fields.Many2one('dog.pension.breed', string="Breed")
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender")
    birth_date = fields.Date(string="Birth Date")
    weight = fields.Float(string="Weight (kg)")
    microchip = fields.Char(string="Microchip")
    notes = fields.Text(string="Notes")

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get('default_line_id')
        if line_id:
            line = self.env['sale.order.line'].browse(line_id)
            res['line_id'] = line.id
            res['owner_id'] = line.order_partner_id.id
        return res

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_create_and_select(self):
        """Create the dog and link it to the sale order line."""
        self.ensure_one()
        if not self.owner_id:
            raise ValidationError("An owner is required to create a dog.")

        dog = self.env['dog.pension.dog'].create({
            'name': self.name,
            'owner_id': self.owner_id.id,
            'breed_id': self.breed_id.id,
            'gender': self.gender,
            'birth_date': self.birth_date,
            'weight': self.weight,
            'microchip': self.microchip,
            'notes': self.notes,
        })

        # Link to the sale order line
        if self.line_id:
            self.line_id.dog_id = dog.id

        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
