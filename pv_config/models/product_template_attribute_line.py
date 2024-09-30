from odoo import models, fields


class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    is_configuration_attribute = fields.Boolean(
        string='Configuration Attribute')
