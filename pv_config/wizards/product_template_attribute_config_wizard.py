from odoo import models, fields, api


def _render_matrix(self, product_templ_id):
    product_tmpl_configuration_ids = []
    old_product_tmpl_configuration_ids = self.product_tmpl_configuration_ids
    if product_templ_id.configuration_attribute_line_header_values and product_templ_id.configuration_attribute_line_values:
        for header_value in product_templ_id.configuration_attribute_line_header_values:
            for value in product_templ_id.configuration_attribute_line_values:
                if self.product_tmpl_configuration_ids:
                    config = old_product_tmpl_configuration_ids.filtered(
                        lambda r: r.configuration_attribute_line_header_value.id == header_value.id and r.configuration_attribute_line_value.id == value.id)
                    if config and len(config) > 0:
                        is_valid_config = config[0].configuration_attribute_is_valid
                    else:
                        is_valid_config = False
                else:
                    is_valid_config = False

                product_tmpl_configuration_ids.append((0, 1, {
                    'configuration_attribute_line_header_value': header_value.id,
                    'configuration_attribute_line_value': value.id,
                    'configuration_attribute_is_valid': is_valid_config,
                }))

    product_templ_id.product_tmpl_configuration_ids = False
    return product_tmpl_configuration_ids


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
        if self.product_tmpl_id:
            ids = _render_matrix(self, self.product_tmpl_id)
            self.product_tmpl_configuration_ids = ids

    def action_configure_product_template_attributes(self):
        self.ensure_one()
