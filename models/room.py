from odoo import api, fields, models


class DogPensionRoom(models.Model):
    _name = 'dog.pension.room'
    _description = 'Dog Pension Room'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string="Room Name", required=True, tracking=True)
    code = fields.Char(string="Code")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
    )

    hallway_ids = fields.One2many(
        'dog.pension.hallway', 'room_id', string="Hallways"
    )
    hallway_count = fields.Integer(
        string="Hallways", compute='_compute_hallway_count'
    )
    kennel_count = fields.Integer(
        string="Kennels", compute='_compute_kennel_count'
    )

    def _compute_hallway_count(self):
        for room in self:
            room.hallway_count = len(room.hallway_ids)

    def _compute_kennel_count(self):
        for room in self:
            room.kennel_count = sum(
                hallway.kennel_count for hallway in room.hallway_ids
            )

    def action_view_hallways(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hallways',
            'res_model': 'dog.pension.hallway',
            'view_mode': 'list,form',
            'domain': [('room_id', '=', self.id)],
            'context': {'default_room_id': self.id},
        }

    def action_view_kennels(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kennels',
            'res_model': 'dog.pension.kennel',
            'view_mode': 'list,form',
            'domain': [('room_id', '=', self.id)],
            'context': {'default_room_id': self.id},
        }
