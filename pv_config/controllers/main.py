from odoo.http import Controller, request, route


class ProductVariantConfiguratorController(Controller):

    @route('/pv_config/get_ptav_is_valid', type='json', auth='user')
    def get_product_template_attribute_value_is_valid(self, ptav_id, selected_header_value_id):
        ptav = request.env['product.template.attribute.value'].browse(ptav_id)
        header = request.env['product.template.attribute.value'].browse(int(selected_header_value_id))
        product_template = ptav.product_tmpl_id
        if product_template.id != header.product_tmpl_id.id:
            return True
        for configuration in product_template.product_tmpl_configuration_ids:
            if (configuration.configuration_attribute_line_header_value == header.product_attribute_value_id and
                    configuration.configuration_attribute_line_value == ptav.product_attribute_value_id):
                return configuration.configuration_attribute_is_valid
        return True

    @route('/pv_config/get_ptal_is_header', type='json', auth='user')
    def get_product_template_attribute_line_is_header(self, product_template_id, ptal_id):
        ptal = request.env['product.template.attribute.line'].browse(ptal_id)
        product_template = request.env['product.template'].browse(product_template_id)
        if (len(product_template.configuration_attribute_line_ids) > 0 and
                product_template.configuration_attribute_line_ids[0].id == ptal.id):
            return True
        return False

    @route('/pv_config/get_ptal_is_line', type='json', auth='user')
    def get_product_template_attribute_line_is_line(self, product_template_id, ptal_id):
        ptal = request.env['product.template.attribute.line'].browse(ptal_id)
        product_template = request.env['product.template'].browse(product_template_id)
        if (len(product_template.configuration_attribute_line_ids) > 0 and
                product_template.configuration_attribute_line_ids[0].id != ptal.id and
                ptal.id in product_template.configuration_attribute_line_ids.ids):
            return True
        return False
