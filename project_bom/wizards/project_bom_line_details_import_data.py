# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _, api
from ..models.project_bom_line_details import TYPES_SELECTION

class ProjectBomLineDetailsImportData(models.TransientModel):
    _name = 'project.bom.line.details.import.data'
    _description = 'Project BOM line details (CAD data file)'

    def _get_type_used_detail(self):
        return TYPES_SELECTION

    import_id = fields.Many2one('project.bom.line.details.import.wizard', string='Import')
    qty = fields.Float(string='Quantity', default=1.0)
    designator = fields.Char(string='Designator')
    default_code = fields.Char(string='Internal reference')
    short_description = fields.Char(string='Technical Description')
    short_description_option = fields.Char(string='Option Description')
    manufacturer_part = fields.Char(string='Manufacturer Part Number')
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description')
    error_message = fields.Text(string='Error Message', readonly=True)
    is_valid = fields.Boolean(string='Not Validated')
    hw_option = fields.Many2one('product.product', string='HW Option',
                                help='Used kit for Project BOM, replacement of component.')
    type = fields.Selection(selection='_get_type_used_detail', string='Type', default='normal')
    semi_product_tmpl_id = fields.Many2one('product.template', related='import_id.product_tmpl_id')
    possible_bom_product_template_attribute_value_ids = fields.Many2many(
        'product.template.attribute.value',
        string="Possible Variants",
        relation='attribute_value_import_wizard_rel',
        compute='_compute_possible_bom_product_template_attribute_value_ids')
    bom_product_template_attribute_value_ids = fields.Many2many(
        'product.template.attribute.value',
        relation='bom_attribute_value_import_wizard_rel',
        string="Apply on Variants",
        ondelete='restrict',
        domain="[('id', 'in', possible_bom_product_template_attribute_value_ids)]",
        help="BOM Product Variants needed to apply this line.")
    x_coordinate = fields.Float(string='X Coordinate')
    y_coordinate = fields.Float(string='Y Coordinate')
    theta = fields.Float(string='Theta')

    @api.depends(
        'semi_product_tmpl_id.attribute_line_ids.value_ids',
        'semi_product_tmpl_id.attribute_line_ids.attribute_id.create_variant',
        'semi_product_tmpl_id.attribute_line_ids.product_template_value_ids.ptav_active',
    )
    def _compute_possible_bom_product_template_attribute_value_ids(self):
        for record in self.filtered(lambda r: r.semi_product_tmpl_id):
            record.possible_bom_product_template_attribute_value_ids = record.semi_product_tmpl_id.valid_product_template_attribute_line_ids._without_no_variant_attributes().product_template_value_ids._only_active()

