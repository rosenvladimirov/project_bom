# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _


class ProductProduct(models.Model):
    _inherit = "product.product"

    # CAD additional information
    short_description = fields.Char('Technical Description',
                                    size=40,
                                    default=lambda self: self.product_tmpl_id.short_description)
    # component_package = fields.Char('Package', related='product_tmpl_id.component_package', store=True)
    # component_value = fields.Float('Value', related='product_tmpl_id.component_value', store=True)
    # component_voltage = fields.Float('Voltage', related='product_tmpl_id.component_voltage', store=True)
    # component_other = fields.Char('Temperature/Tolerance', related='product_tmpl_id.component_other', store=True)
    #
    # x_coordinate = fields.Float(string='X Coordinate', default=lambda self: self.product_tmpl_id.x_coordinate)
    # y_coordinate = fields.Float(string='Y Coordinate', default=lambda self: self.product_tmpl_id.y_coordinate)
    component_type_id = fields.Many2one('component.definition.properties',
                                        related='product_tmpl_id.component_type_id',
                                        store=True)
    component_properties = fields.Properties('Component technical data',
                                             definition='component_type_id.component_properties_definition')

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        short_description = False
        positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
        if name and domain is not None:
            for arg in domain:
                if isinstance(arg, (list, tuple)) and arg[0] == 'short_description':
                    short_description = True
                    break
        if name and operator in positive_operators and not short_description:
            domain += ['|', ('short_description', operator, name),
                       ('product_tmpl_id.short_description', operator, name)]
        return super()._name_search(name, domain=domain, operator=operator, limit=limit, order=order)
