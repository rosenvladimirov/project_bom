# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ProjectBomLineDetails(models.Model):
    _name = 'project.bom.line.details'
    _description = 'Project BOM line details (CAD data file)'

    project_bom_id = fields.Many2one('project.mrp.bom',
                                     'Parent Project BOM',
                                     index=True,
                                     ondelete='cascade',
                                     required=True)
    project_bom_line_id = fields.Many2one('project.mrp.bom.line',
                                          'Parent Project BOM Line',
                                          index=True,
                                          ondelete='cascade',
                                          required=True)

    sequence = fields.Integer(string='Sequence', default=10)
    final_product_tmpl_id = fields.Many2one('product.template',
                                            string='Final Product Template',
                                            related='project_bom_id.product_tmpl_id')
    final_product_id = fields.Many2one('product.product',
                                       string='Final Product',
                                       related='project_bom_id.product_id',
                                       )
    possible_bom_product_template_attribute_value_ids = fields.Many2many(
        related='project_bom_id.possible_product_template_attribute_value_ids')
    bom_product_template_attribute_value_ids = fields.Many2many(
        'product.template.attribute.value', string="Apply on Variants", ondelete='restrict',
        domain="[('id', 'in', possible_bom_product_template_attribute_value_ids)]",
        help="BOM Product Variants needed to apply this line.")

    designator = fields.Char(string='Designator')
    product_id =  fields.Many2one('product.product', string='Component',
                                  help='Used component for Project BOM, '
                                       'if use HW option please discard this product.')
    hw_option = fields.Many2one('product.product', string='HW Option',
                                help='Used kit for Project BOM, replacement of component.')

    default_code = fields.Char(string='Internal reference',
                               related='product_id.default_code',
                               store=True)
    short_description = fields.Char(string='Technical Description',
                                    related="product_id.short_description",
                                    store=True)
    domain_short_description = fields.Binary(default=[],
                                             compute="_compute_short_descriptions",
                                             string='Domain Short Description')

    description = fields.Char(string='Description', related='product_id.display_name', store=True)

    type = fields.Selection([
        ('bom', 'BOM'),
        ('lot', 'Lot'),
        ('kit', 'Kit'),
    ], string='Type'
    )
    used_in_operation = fields.Char(string='Used In Operation')

    # Additional fields for EuroPlacer CAD compatibility
    x_coordinate = fields.Float(string='X Coordinate', related='product_id.x_coordinate', store=True)
    y_coordinate = fields.Float(string='Y Coordinate', related='product_id.y_coordinate', store=True)
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
                record.short_description = record.product_id.short_description


    @api.depends('short_description')
    def _compute_short_descriptions(self):
        for record in self:
            if record.short_description:
                found_products = self.env['product.product']. \
                    search([('short_description', '=', record.short_description)])
                if found_products:
                    record.product_id = found_products[0].id
                    record.domain_short_description = [('id', 'in', found_products.ids)]
                else:
                    record.domain_short_description = []
            else:
                record.domain_short_description = []

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            project_bom_id = self.env['project.mrp.bom'].browse([vals['project_bom_id']])
            if not vals.get('project_bom_line_id', False):
                bom_id = self.env['mrp.bom'].search([
                    ('product_tmpl_id', '=', project_bom_id.product_tmpl_id.id), "|",
                    ('product_id', '=', project_bom_id.product_id.id),
                    ('product_id', '=', False)
                ])
                if not bom_id:
                    bom_id = self.env['mrp.bom'].create({
                        'product_tmpl_id': project_bom_id.product_tmpl_id.id,
                        'product_id': project_bom_id.product_id.id,
                    })
                project_bom_line_id = self.env['project.mrp.bom.line'].search([
                    ('id', '=', vals['project_bom_line_id']),
                ])
                if not project_bom_line_id:
                    project_bom_line_id = self.env['project.mrp.bom.line'].search([
                        ('project_bom_id', '=', project_bom_id.id), "|",
                        ('project_product_id', '=', vals['product_id']),
                        ('bom_line_id.product_id', '=', vals['product_id'])
                    ])
                if not project_bom_line_id:
                    project_bom_line_id = self.env['project.mrp.bom.line'].create({
                        'project_product_id': vals['product_id'],
                        'project_bom_id': vals['project_bom_id'],
                        'product_id': vals['product_id'],
                        'bom_id': bom_id.id,
                    })
                vals['project_bom_line_id'] = project_bom_line_id.id
        _logger.info(vals_list)
        return super().create(vals_list)

    def unlink(self):
        for record in self:
            project_bom_line_ids = record.project_bom_id.project_bom_line_ids.\
                filtered(lambda r: r.product_id == record.product_id)
            if len(project_bom_line_ids) == 1:
                project_bom_line_ids.unlink()
        return super().unlink()
