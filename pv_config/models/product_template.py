from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    configuration_attribute_line_ids = fields.One2many(
        'product.template.attribute.line',
        'product_tmpl_id',
        order='sequence',
        string='Configuration Attributes',
        domain=[('is_configuration_attribute', '=', True)],
    )

    # get value_ids of configuration_attribute_line_ids first attribute line ordered by sequence
    configuration_attribute_line_header_values = fields.Many2many(
        'product.attribute.value',
        compute='_compute_configuration_attribute_line_header_values',
        string='Configuration Attribute Line Header Values',
    )

    def _compute_configuration_attribute_line_header_values(self):
        for record in self:
            if record.configuration_attribute_line_ids and record.configuration_attribute_line_ids[0].value_ids:
                record.configuration_attribute_line_header_values = record.configuration_attribute_line_ids[0].value_ids
            else:
                record.configuration_attribute_line_header_values = False

    # get all value_ids of configuration_attribute_line_ids rest attribute lines ordered by sequence
    configuration_attribute_line_values = fields.Many2many(
        'product.attribute.value',
        compute='_compute_configuration_attribute_line_values',
        string='Configuration Attribute Line Values',
    )

    def _compute_configuration_attribute_line_values(self):
        for record in self:
            new_lines = record.configuration_attribute_line_ids[1:].mapped('value_ids')
            record.configuration_attribute_line_values = new_lines

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        if 'attribute_line_ids' in vals:
            self.product_tmpl_configuration_ids.unlink()
        return res

    product_tmpl_configuration_ids = fields.Many2many(
        'prod.templ.config',
        string='Product Template Configurations',
    )

    def action_open_product_configurator(self):
        self.ensure_one()
        wiz = self.env['prod.var.config.wizard'].create({
            'product_tmpl_id': self.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Configurator',
            'res_model': 'prod.var.config.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wiz.id,
        }
