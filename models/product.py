from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_dog_pension_service = fields.Boolean(
        string="Is Dog Pension Service",
        help="Check if this product represents a dog pension stay.",
    )
    dog_pension_daily_rate = fields.Float(
        string="Daily Rate",
        help="Price per day for the stay (informational; used to prefill price).",
    )
