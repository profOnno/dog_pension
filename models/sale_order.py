from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_dog_pension = fields.Boolean(
        string="Is Dog Pension Order",
        compute='_compute_is_dog_pension',
        store=True,
    )
    dog_stay_ids = fields.One2many(
        'dog.pension.stay',
        'sale_order_id',
        string="Dog Stays",
    )
    dog_stay_count = fields.Integer(
        string="Dog Stays",
        compute='_compute_dog_stay_count',
    )

    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------

    @api.depends('order_line.product_id')
    def _compute_is_dog_pension(self):
        for order in self:
            order.is_dog_pension = any(
                line.product_id.is_dog_pension_service
                for line in order.order_line
            )

    def _compute_dog_stay_count(self):
        for order in self:
            order.dog_stay_count = len(order.dog_stay_ids)

    # ------------------------------------------------------------------
    # Onchange: reset dogs when the customer changes
    # ------------------------------------------------------------------

    @api.onchange('partner_id')
    def _onchange_partner_id_reset_dogs(self):
        for line in self.order_line:
            if line.dog_id and line.dog_id.owner_id != self.partner_id:
                line.dog_id = False

    # ------------------------------------------------------------------
    # Validation + confirmation
    # ------------------------------------------------------------------

    def _check_dog_pension_lines(self):
        """Validate that every pension line has a dog and dates."""
        for order in self:
            for line in order.order_line:
                if not line.product_id.is_dog_pension_service:
                    continue
                if not line.dog_id:
                    raise ValidationError(
                        "Select a dog on every line for '%s' before confirming."
                        % line.product_id.name
                    )
                if not line.stay_start_date or not line.stay_end_date:
                    raise ValidationError(
                        "Fill in the check-in and check-out dates for '%s' "
                        "(dog: %s) before confirming."
                        % (line.product_id.name, line.dog_id.name)
                    )

    def action_confirm(self):
        self._check_dog_pension_lines()
        res = super().action_confirm()
        for order in self:
            for stay in order.dog_stay_ids:
                if stay.state == 'draft':
                    stay.action_confirm()
        return res

    # ------------------------------------------------------------------
    # Button action
    # ------------------------------------------------------------------

    def action_view_dog_stays(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'dog_pension.action_dog_pension_stay'
        )
        action['domain'] = [('sale_order_id', '=', self.id)]
        action['context'] = {'default_sale_order_id': self.id}
        return action


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ------------------------------------------------------------------
    # New fields
    # ------------------------------------------------------------------

    # Odoo 19: no string-based context on fields (crashes web_read).
    # Owner default is handled by the quick-create wizard instead.
    dog_id = fields.Many2one(
        'dog.pension.dog',
        string="Dog",
        domain="[('owner_id', '=', order_partner_id)]",
        help="Dog the stay is booked for",
    )
    stay_start_date = fields.Datetime(string="Stay Check-in")
    stay_end_date = fields.Datetime(string="Stay Check-out")
    stay_duration_days = fields.Float(
        string="Stay Duration (days)",
        compute='_compute_stay_duration',
        store=True,
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('stay_start_date', 'stay_end_date')
    def _compute_stay_duration(self):
        for line in self:
            if line.stay_start_date and line.stay_end_date:
                delta = line.stay_end_date - line.stay_start_date
                line.stay_duration_days = max(
                    0.0, delta.total_seconds() / 86400.0
                )
            else:
                line.stay_duration_days = 0.0

    # ------------------------------------------------------------------
    # Onchange: quantity, price, description
    # ------------------------------------------------------------------

    @api.onchange('product_id')
    def _onchange_product_id_dog_pension(self):
        """When a pension product is chosen, prefill the price from the daily rate."""
        if self.product_id and self.product_id.is_dog_pension_service:
            if self.product_id.dog_pension_daily_rate:
                self.price_unit = self.product_id.dog_pension_daily_rate
            # If dates are already filled, recalculate the quantity
            if self.stay_start_date and self.stay_end_date:
                delta = self.stay_end_date - self.stay_start_date
                self.product_uom_qty = max(
                    1.0, delta.total_seconds() / 86400.0
                )

    @api.onchange('stay_start_date', 'stay_end_date', 'product_id')
    def _onchange_stay_dates(self):
        """Recalculate quantity and price when stay dates change."""
        if not (self.product_id and self.product_id.is_dog_pension_service):
            return
        if self.stay_start_date and self.stay_end_date:
            delta = self.stay_end_date - self.stay_start_date
            days = max(1.0, delta.total_seconds() / 86400.0)
            self.product_uom_qty = days
            if self.product_id.dog_pension_daily_rate:
                self.price_unit = self.product_id.dog_pension_daily_rate
        else:
            # No dates yet: keep it at a single day so the total doesn't get stuck
            self.product_uom_qty = 1.0

    @api.onchange('product_id', 'dog_id', 'stay_start_date', 'stay_end_date')
    def _onchange_build_description(self):
        """Build a customer-facing description with dog and dates.

        Only overwrite the description if it is still the default product name,
        so manual edits are preserved.
        """
        if not (self.product_id and self.product_id.is_dog_pension_service):
            return
        default = self.product_id.get_product_multiline_description_sale()
        if self.name and self.name != default:
            return
        parts = [default]
        if self.dog_id:
            parts.append(f"Dog: {self.dog_id.name}")
        if self.stay_start_date:
            parts.append(f"Check-in: {self.stay_start_date}")
        if self.stay_end_date:
            parts.append(f"Check-out: {self.stay_end_date}")
        if self.stay_duration_days:
            parts.append(f"Duration: {self.stay_duration_days:.1f} days")
        self.name = "\n".join(parts)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('dog_id', 'stay_start_date', 'stay_end_date')
    def _check_dog_stay_dates(self):
        for line in self:
            if not line.product_id.is_dog_pension_service:
                continue
            if line.dog_id and line.stay_start_date and line.stay_end_date:
                if line.stay_end_date <= line.stay_start_date:
                    raise ValidationError(
                        "Check-out date must be after Check-in date for dog '%s'."
                        % line.dog_id.name
                    )

    # ------------------------------------------------------------------
    # Quick-create wizard button
    # ------------------------------------------------------------------

    def action_quick_create_dog(self):
        """Open the quick-create wizard for a new dog."""
        self.ensure_one()
        if not self.order_partner_id:
            raise ValidationError(
                "Please select a customer on the order first."
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Dog',
            'res_model': 'dog.pension.dog.quick.create',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
            },
        }

    # ------------------------------------------------------------------
    # Stay sync
    # ------------------------------------------------------------------

    def _prepare_dog_stay_vals(self):
        self.ensure_one()
        return {
            'dog_id': self.dog_id.id,
            'start_date': self.stay_start_date,
            'end_date': self.stay_end_date,
            'sale_order_id': self.order_id.id,
            'sale_order_line_id': self.id,
            'company_id': self.order_id.company_id.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_dog_stays()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in (
            'dog_id', 'stay_start_date', 'stay_end_date', 'product_id',
        )):
            self._sync_dog_stays()
        return res

    def unlink(self):
        stays = self.env['dog.pension.stay'].search([
            ('sale_order_line_id', 'in', self.ids)
        ])
        stays.unlink()
        return super().unlink()

    def _sync_dog_stays(self):
        """Create, update or remove the linked dog.pension.stay records."""
        for line in self:
            existing = self.env['dog.pension.stay'].search([
                ('sale_order_line_id', '=', line.id)
            ])
            if (
                line.dog_id
                and line.stay_start_date
                and line.stay_end_date
                and line.product_id.is_dog_pension_service
            ):
                vals = line._prepare_dog_stay_vals()
                if existing:
                    existing.write(vals)
                else:
                    self.env['dog.pension.stay'].create(vals)
            elif existing:
                existing.unlink()
