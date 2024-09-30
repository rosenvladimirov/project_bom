# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import models, fields, _, api
from .project_bom_line_details_import_wizard import MIMETYPES
_logger = logging.getLogger(__name__)


class ProjectBomLineDetailsImportData(models.TransientModel):
    _name = 'project.bom.line.details.import.data'
    _description = 'Project BOM line details (CAD data file)'

    def _get_type_used_detail(self):
        return [
            ('normal', _('Normal bom')),
            ('kit', _('Kit bom')),
        ]

    import_id = fields.Many2one('project.bom.line.details.import.wizard', string='Import')
    qty = fields.Float(string='Quantity', default=1.0)
    designator = fields.Char(string='Designator')
    default_code = fields.Char(string='Internal reference')
    short_description = fields.Char(string='Technical Description')
    short_description_option = fields.Char(string='Option Description')
    short_description_semi_product = fields.Char(string='Semi-product Short Description')
    manufacturer_part = fields.Char(string='Manufacturer Part Number')
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description')
    error_message = fields.Text(string='Error Message', readonly=True)
    is_valid = fields.Boolean(string='Not Validated')
    hw_option = fields.Many2one('product.product', string='HW Option',
                                help='Used kit for Project BOM, replacement of component.')
    type = fields.Selection(selection='_get_type_used_detail', string='Type', default='normal')
    semi_product_tmpl_id = fields.Many2one('product.template', related='import_id.semi_product_tmpl_id', store=True)
    semi_product_id = fields.Many2one('product.product', related='import_id.semi_product_id', store=True)
    possible_bom_product_template_attribute_value_ids = fields.Many2many(
        'product.template.attribute.value',
        string="Possible Variants",
        relation='attribute_value_import_wizard_rel',
        compute='_compute_possible_bom_product_template_attribute_value_ids',
        store=True)
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

    x_coordinate_fiducial_1 = fields.Float(string='X Coordinate base on fiducial 1')
    y_coordinate_fiducial_1 = fields.Float(string='Y Coordinate base on fiducial 1')
    x_coordinate_fiducial_1_txt = fields.Float(string='X Coordinate base on fiducial 1 pnp file')
    y_coordinate_fiducial_1_txt = fields.Float(string='Y Coordinate base on fiducial 1 pnp file')
    theta_txt = fields.Float(string='Theta pnp file')

    @api.depends(
        'semi_product_tmpl_id.attribute_line_ids.value_ids',
        'semi_product_tmpl_id.attribute_line_ids.attribute_id.create_variant',
        'semi_product_tmpl_id.attribute_line_ids.product_template_value_ids.ptav_active',
    )
    def _compute_possible_bom_product_template_attribute_value_ids(self):
        for record in self:
            _logger.info(f"{record.semi_product_tmpl_id}")
            if record.semi_product_tmpl_id:
                semi_product_tmpl_id = record.semi_product_tmpl_id
                record.possible_bom_product_template_attribute_value_ids = semi_product_tmpl_id.valid_product_template_attribute_line_ids._without_no_variant_attributes().product_template_value_ids._only_active()


    @api.onchange('is_valid')
    def onchange_is_valid(self):
        for record in self.filtered(lambda r: r.is_valid):
            import_id = record.import_id
            import_id.validated = True
            for line in import_id.line_details:
                if not line.is_valid:
                    import_id.validated = False
                    break
