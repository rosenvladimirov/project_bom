# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError
from odoo.modules.module import current_test

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
    semi_product_tmpl_id = fields.Many2one('product.template',
                                           string='Semi Product Template')
    semi_product_id = fields.Many2one('product.product',
                                      string='Semi Product')

    default_code = fields.Char(string='Internal reference',
                               related='product_id.default_code',
                               store=True)
    short_description = fields.Char(string='Technical Description',
                                    related="product_id.short_description",
                                    store=True)

    product_qty = fields.Float(string='Quantity', default=1.0)

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

    @api.onchange('product_id')
    def onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.default_code = record.product_id.default_code
                record.description = record.product_id.display_name
                record.short_description = record.product_id.short_description

    @api.onchange('short_description')
    def onchange_short_description(self):
        for record in self.filtered(lambda r: r.short_description):
            found_products = self.env['product.product']. \
                search([('short_description', '=', record.short_description)])
            if not found_products:
                raise UserError(_("Missing product with technical description: %s") % record.short_description)

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

    def sterilise_vals(self, vals, current_project_bom_line_id):
        if not vals:
            return vals

        _logger.info(f"Values: {vals}")
        if not vals.get('project_bom_id'):
            project_bom_id = self.project_bom_id
        else:
            project_bom_id = self.env['project.mrp.bom'].browse([vals['project_bom_id']])

        # Base (final) product in project bom
        final_product_bom_id = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', project_bom_id.product_tmpl_id.id), "|",
            ('product_id', '=', project_bom_id.product_id.id),
            ('product_id', '=', False)
        ])
        if not final_product_bom_id:
            _logger.info(f"# Base (final) product in project bom: {project_bom_id.product_tmpl_id}")
            final_product_bom_id = self.env['mrp.bom'].create({
                'product_tmpl_id': project_bom_id.product_tmpl_id.id,
                'product_id': project_bom_id.product_id.id,
                'code': _(f"draft_{project_bom_id.code}")
            })

        # Semi product
        semi_product_tmpl_id = self.env['product.template']
        semi_product_id = self.env['product.product']
        semi_product_bom_id = self.env['mrp.bom']
        if vals.get('semi_product_tmpl_id', False) or vals.get('semi_product_id', False):
            if vals.get('semi_product_id', False):
                semi_product_id = self.env['product.product'].browse(vals['semi_product_id'])
            if vals.get('semi_product_tmpl_id', False):
                semi_product_tmpl_id = self.env['product.template'].browse(vals['semi_product_tmpl_id'])
            if semi_product_id and not semi_product_tmpl_id:
                semi_product_tmpl_id = semi_product_id.product_tmpl_id
            semi_product_bom_id = self.env['mrp.bom'].search([
                ('product_tmpl_id', '=', semi_product_tmpl_id.id), "|",
                ('product_id', '=', semi_product_id.id),
                ('product_id', '=', False)
            ])
            if semi_product_tmpl_id and not semi_product_bom_id:
                _logger.info(f"# Semi product: {semi_product_tmpl_id}")
                semi_product_bom_id = self.env['mrp.bom'].create({
                    'product_tmpl_id': semi_product_tmpl_id.id,
                    'product_id': vals.get('semi_product_id', False),
                    'code': _(f"draft_{project_bom_id.code}")
                })

        #  Kits
        hw_option = self.env['product.product']
        hw_option_bom_id = self.env['mrp.bom']
        if vals.get('hw_option', False):
            hw_option = self.env['product.product'].browse(vals.get['hw_option'])
            hw_option_bom_id = self.env['mrp.bom'].search([
                ('product_id', '!=', False),
                ('product_id', '=', hw_option.id),
            ])
            if hw_option and not hw_option_bom_id:
                _logger.info(f"# Kits: {hw_option}")
                hw_option_bom_id = self.env['mrp.bom'].create({
                    'product_tmpl_id': hw_option.product_tmpl_id.id,
                    'code': _(f"draft_{project_bom_id.code}")
                })

        if hw_option and semi_product_bom_id:
            # First to check the kit is included in semi product
            if semi_product_bom_id:
                semi_product_bom_line_ids = semi_product_bom_id.mapped('bom_line_ids')
                semi_product_bom_line_id = semi_product_bom_line_ids.filtered(lambda r: r.product_id == hw_option)
                if not semi_product_bom_line_id:
                    semi_product_bom_id.bom_line_ids = [Command.create({
                        'product_id': hw_option.id,
                        'product_qty': 1.0,
                    })]
                else:
                    semi_product_bom_line_id.write({
                        'product_qty': semi_product_bom_line_id.product_qty + 1.0,
                    })
            # Next to search for line in project bom
            project_bom_line_id = self.env['project.mrp.bom.line'].search([
                ('project_bom_id', '=', project_bom_id.id),
                ('semi_product_tmpl_id', '=', hw_option.product_tmpl_id.id),
                "|",
                ('semi_product_id', '=', hw_option.id),
                ('semi_product_id', '=', False),
                "|",
                ('project_product_id', '=', vals['product_id']),
                ('bom_line_id.product_id', '=', vals['product_id'])
            ])
            bom_id = hw_option_bom_id
        elif semi_product_bom_id and not hw_option:
            project_bom_line_id = self.env['project.mrp.bom.line'].search([
                ('project_bom_id', '=', project_bom_id.id),
                ('semi_product_tmpl_id', '=', semi_product_tmpl_id.id),
                "|",
                ('semi_product_id', '=', semi_product_id.id),
                ('semi_product_id', '=', False),
                "|",
                ('project_product_id', '=', vals['product_id']),
                ('bom_line_id.product_id', '=', vals['product_id'])
            ])
            bom_id = semi_product_bom_id
        else:
            project_bom_line_id = self.env['project.mrp.bom.line'].search([
                ('project_bom_id', '=', project_bom_id.id),
                ('semi_product_tmpl_id', '=', False),
                "|",
                ('project_product_id', '=', vals['product_id']),
                ('bom_line_id.product_id', '=', vals['product_id'])
            ])
            bom_id = final_product_bom_id

        if current_project_bom_line_id and current_project_bom_line_id != project_bom_line_id:
            current_project_bom_line_id.unlink()
            current_project_bom_line_id = self.env['project.mrp.bom.line']

        if current_project_bom_line_id and project_bom_line_id == current_project_bom_line_id:
            current_project_bom_line_id.write({
                'project_product_qty': current_project_bom_line_id.project_product_qty + 1.0,
            })
        elif not project_bom_line_id:
            project_bom_line_id = self.env['project.mrp.bom.line'].create({
                'project_bom_id': project_bom_id.id,
                'semi_product_tmpl_id': hw_option and hw_option.product_tmpl_id.id or semi_product_tmpl_id and semi_product_tmpl_id.id or False,
                'semi_product_id': hw_option and hw_option.id or semi_product_id and semi_product_id.id or False,
                'project_product_id': vals['product_id'],
                'product_id': vals['product_id'],
                'name': vals['description'],
                'bom_id': bom_id.id,
            })

        else:
            project_bom_line_id.write({
                'project_product_qty': project_bom_line_id.project_product_qty + 1.0,
                'product_qty': project_bom_line_id.product_qty + 1.0,
                'bom_id': bom_id.id,
            })
        vals['project_bom_line_id'] = project_bom_line_id.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.sterilise_vals(vals, self.env['project.mrp.bom.line'])

        res = super().create(vals_list)
        for record, vals in zip(res, vals_list):
            record.project_bom_id.project_bom_line_details_ids.write({})
        return res

    def write(self, vals):
        return super().write(self.sterilise_vals(vals, self))

    def unlink(self):
        for record in self:
            project_bom_line_ids = record.project_bom_id.project_bom_line_ids.\
                filtered(lambda r: r == record.project_bom_line_id)
            if len(project_bom_line_ids) == 1:
                project_bom_line_ids.unlink()
        return super().unlink()
