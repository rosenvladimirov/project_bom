from odoo import models, fields, api


class ProductTemplateAttributeConfig(models.Model):
    _name = 'prod.var.config.wizard'
    _description = 'Product Template Attribute Configuration'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        required=True,
        ondelete='cascade',
    )

    product_tmpl_configuration_ids = fields.Many2many(
        'prod.templ.config',
        related='product_tmpl_id.product_tmpl_configuration_ids',
        readonly=False,
    )

    @api.model
    def create(self, vals):
        record = super(ProductTemplateAttributeConfig, self).create(vals)
        record.render_matrix()
        return record

    def render_matrix(self):
        if self.product_tmpl_configuration_ids:
            return
        product_tmpl_configuration_ids = []
        if self.product_tmpl_id and self.product_tmpl_id.configuration_attribute_line_header_values and self.product_tmpl_id.configuration_attribute_line_values:
            for header_value in self.product_tmpl_id.configuration_attribute_line_header_values:
                for value in self.product_tmpl_id.configuration_attribute_line_values:
                    product_tmpl_configuration_ids.append((0, 0, {
                        'configuration_attribute_line_header_value': header_value.id,
                        'configuration_attribute_line_value': value.id,
                        'configuration_attribute_is_valid': False,
                    }))
        self.product_tmpl_id.product_tmpl_configuration_ids = product_tmpl_configuration_ids

    def action_configure_product_template_attributes(self):
        self.ensure_one()
