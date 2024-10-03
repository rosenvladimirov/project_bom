from odoo import models, fields


class ProductTemplateConfiguration(models.Model):
    _name = 'prod.templ.config'
    _description = 'Product Template Configuration'

    configuration_attribute_line_header_value = fields.Many2one(
        'product.attribute.value',
        string='Configuration Attribute Line Header Value')

    configuration_attribute_line_value = fields.Many2one(
        'product.attribute.value',
        string='Configuration Attribute Line Value')

    configuration_attribute_is_valid = fields.Boolean(
        string='Configuration Attribute Is Valid')
