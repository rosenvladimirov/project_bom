# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from email.policy import default

from odoo import models, fields, api
from odoo.tools.populate import compute


class ProjectBomLineDetails(models.Model):
    _name = 'project.bom.line.details'
    _description = 'Project BOM line details (CAD data file)'

    sequence = fields.Integer(string='Sequence', default=10)

    designator = fields.Char(string='Designator')
    product_id = fields.Many2one('product.product', string='Product')
    default_code = fields.Char(string='Internal reference', related='product_id.default_code', store=True)
    description = fields.Char(string='Description', related='product_id.display_name', store=True)
    short_description = fields.Char(string='Short Description')
    domain_short_description = fields.Binary(default=[], compute="_compute_short_descriptions", string='Domain Short Description')
    sequence = fields.Integer(string='Sequence')
    type = fields.Selection([
        ('bom', 'BOM'),
        ('lot', 'Lot'),
        ('kit', 'Kit'),
    ], string='Type'
    )
    used_in_product = fields.Char(string='Used in Product')
    used_in_operation = fields.Char(string='Used In Operation')
    product_variant = fields.Char(string='Product Variant')
    hw_option = fields.Char(string='HW Option')

    # Additional fields for Europlacer compatibility
    x_coordinate = fields.Float(string='X Coordinate')
    y_coordinate = fields.Float(string='Y Coordinate')
    theta = fields.Float(string='Theta')
    pattern_reference = fields.Char(string='Pattern Reference')
    pattern_call = fields.Char(string='Pattern Call')
    fiducial_mark = fields.Char(string='Fiducial Mark')
    rejection_mark = fields.Char(string='Rejection Mark')
    component_test = fields.Boolean(string='Component Test')
    optimization_mode = fields.Selection([
        ('closest_pair', 'Closest Pair'),
        ('band', 'Band'),
        ('closest_pair_2', 'Closest Pair 2'),
    ], string='Optimization Mode')
    auto_adaptive_sequencing = fields.Boolean(string='Auto Adaptive Sequencing')
    stacking_board_number = fields.Integer(string='Stacking Board Number')

    def onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.default_code = record.product_id.default_code
                record.description = record.product_id.display_name


    @api.depends('short_description')
    def _compute_short_descriptions(self):
        for record in self:
            if record.short_description:
                found_products = (
                    self.env['product.product'].search([('short_description', '=', record.short_description)]))

                if found_products:
                    record.domain_short_description = [('id', 'in', found_products.ids)]
