# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.tools.pdf import add_banner


class ProjectBomLineDetailsImportData(models.TransientModel):
    _name = 'project.bom.line.details.import.data'
    _description = 'Project BOM line details (CAD data file)'

    import_id = fields.Many2one('project.bom.line.details.import.wizard', string='Import')
    qty = fields.Float(string='Quantity', default=1.0)
    designator = fields.Char(string='Designator')
    default_code = fields.Char(string='Internal reference')
    short_description = fields.Char(string='Technical Description')
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description')
    error_message = fields.Text(string='Error Message', readonly=True)
    not_validated = fields.Boolean(string='Not Validated')
