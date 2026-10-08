from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_dog_owner = fields.Boolean(string="Is a Dog Owner", default=False)
    dog_ids = fields.One2many('dog.pension.dog', 'owner_id', string="Dogs")
    dog_count = fields.Integer(string="Number of Dogs", compute='_compute_dog_count')

    def _compute_dog_count(self):
        for partner in self:
            partner.dog_count = len(partner.dog_ids)
