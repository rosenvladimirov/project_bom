from odoo.http import Controller, request, route


class ProductVariantConfiguratorController(Controller):
    @route('/pv_config/get_ptav_is_valid', type='json', auth='user')
    def get_product_template_attribute_value_is_valid(self, ptav_id):
        product_template_attribute_value = request.env['product.template.attribute.value'].browse(
            ptav_id)
        if product_template_attribute_value.is_header:
            return True
        if not product_template_attribute_value.configuration_product_template_attribute_value or not product_template_attribute_value.configuration_product_template_attribute_value.id:
            return True
        return product_template_attribute_value.configuration_product_template_attribute_value.configuration_attribute_is_valid

    @route('/pv_config/get_headers', type='json', auth='user')
    def get_headers(self, product_template_id):
        product_template = request.env['product.template'].browse(product_template_id)
        header_values = product_template.configuration_attribute_line_header_values
        header_product_template_attribute_values = []
        for header_value in header_values:
            val = request.env['product.template.attribute.value'].search([
                ('product_tmpl_id', '=', product_template.id),
                ('product_attribute_value_id', '=', header_value.id),
            ])
            if val:
                header_product_template_attribute_values.append(val[0])
        return header_product_template_attribute_values

    @route('/pv_config/get_values_for_selected_header', type='json', auth='user')
    def get_values_for_selected_header(self, product_template_id, header_id):
        product_template = request.env['product.template'].browse(product_template_id)
        header = request.env['product.attribute.value'].browse(header_id)
        config = product_template.product_tmpl_configuration_ids
        values = config.filtered(lambda r: r.configuration_attribute_line_header_value.id == header.id).mapped(
            'configuration_attribute_line_value')
        value_product_template_attribute_values = request.env['product.template.attribute.value'].search([
            ('product_tmpl_id', '=', product_template.id),
            ('product_attribute_value_id', 'in', values.ids)
        ])
        return value_product_template_attribute_values
