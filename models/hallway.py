from odoo import api, fields, models


class DogPensionHallway(models.Model):
    _name = 'dog.pension.hallway'
    _description = 'Dog Pension Hallway'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'room_id, name'

    name = fields.Char(string="Hallway Name", required=True, tracking=True)
    code = fields.Char(string="Code")
    room_id = fields.Many2one(
        'dog.pension.room',
        string="Room",
        required=True,
        ondelete='cascade',
    )
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        related='room_id.company_id',
        store=True,
    )

    kennel_ids = fields.One2many(
        'dog.pension.kennel', 'hallway_id', string="Kennels"
    )
    kennel_count = fields.Integer(
        string="Kennels", compute='_compute_kennel_count'
    )

    def _compute_kennel_count(self):
        for hallway in self:
            hallway.kennel_count = len(hallway.kennel_ids)

    def action_view_kennels(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kennels',
            'res_model': 'dog.pension.kennel',
            'view_mode': 'list,form',
            'domain': [('hallway_id', '=', self.id)],
            'context': {'default_hallway_id': self.id},
        }
