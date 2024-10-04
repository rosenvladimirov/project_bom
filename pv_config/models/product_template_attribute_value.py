from email.policy import default

from odoo import models, fields, api
from odoo.tools.populate import compute


class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    configuration_product_template_attribute_value = fields.Many2one(
        'prod.templ.config',
        string='Configuration Product Template Attribute Value',
    )

    is_header = fields.Boolean(
        string='Is Header',
        default=False,
    )
