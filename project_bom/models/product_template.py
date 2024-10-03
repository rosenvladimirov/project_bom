# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = "product.category"

    product_type_id = fields.Many2one('project.product.types', 'Product Type')

    def get_product_type_id(self):
        product_type_id = False
        for record in self:
            product_type_id = record.product_type_id
            parent_id = record.parent_id
            while parent_id:
                product_type_id = parent_id.product_type_id and parent_id.product_type_id or product_type_id
                parent_id = parent_id.parent_id
        return product_type_id


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_type_id = fields.Many2one('project.product.types', 'Product Type')
    direct_standard_price = fields.Float(
        'Cost',
        compute='_compute_direct_standard_price',
        inverse='_set_direct_standard_price',
        search='_search_direct_standard_price')
    project_bom_count = fields.Integer(
        '# Bill of Material',
        compute='_compute_project_bom_count')

    # CAD additional information
    short_description = fields.Char('Technical Description',
                                    size=40,
                                    compute='_compute_short_description',
                                    inverse='_inverse_short_description',
                                    store=True)
    component_type_id = fields.Many2one('component.definition.properties',
                                        compute='_compute_component_type_id',
                                        inverse='_inverse_component_type_id',
                                        string='Component Type',
                                        store=True)
    component_properties = fields.Properties('Component technical data',
                                             compute='_compute_component_properties',
                                             inverse='_inverse_component_properties',
                                             definition='component_type_id.component_properties_definition',
                                             store=True,
                                             )

    # component_package = fields.Char('Package')
    # component_value = fields.Float('Value')
    # component_voltage = fields.Float('Voltage')
    # component_other = fields.Char('Temperature/Tolerance')
    # x_coordinate = fields.Float(string='X Coordinate')
    # y_coordinate = fields.Float(string='Y Coordinate')

    def _compute_project_bom_count(self):
        read_group_res = self.env['project.mrp.bom'].read_group([('product_tmpl_id', 'in', self.ids)],
                                                                ['product_tmpl_id'],
                                                                ['product_tmpl_id'])
        mapped_data = dict([(data['product_tmpl_id'][0], data['product_tmpl_id_count']) for data in read_group_res])
        for product in self:
            product.project_bom_count = mapped_data.get(product.id, 0)

    @api.depends('product_variant_ids', 'product_variant_ids.direct_standard_price')
    def _compute_direct_standard_price(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.direct_standard_price = template.product_variant_ids.direct_standard_price
        for template in (self - unique_variants):
            template.direct_standard_price = 0.0

    def _set_direct_standard_price(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.direct_standard_price = self.direct_standard_price

    def _search_direct_standard_price(self, operator, value):
        products = self.env['product.product'].search([('direct_standard_price', operator, value)], limit=None)
        return [('id', 'in', products.mapped('product_tmpl_id').ids)]

    @api.depends('product_variant_id.component_type_id')
    def _compute_component_type_id(self):
        for record in self:
            record.component_type_id = record.product_variant_id.component_type_id

    def _inverse_component_type_id(self):
        for record in self:
            for product_id in record.product_variant_ids:
                if product_id.component_type_id != record.component_type_id:
                    product_id.write({'component_properties': False})
                product_id.component_type_id = record.component_type_id

    @api.depends('product_variant_ids.component_properties')
    def _compute_component_properties(self):
        for record in self:
            record.component_properties = record.product_variant_ids[0].component_properties

    def _inverse_component_properties(self):
        for record in self:
            if record.product_variant_count == 1 and \
                    record.component_properties and \
                    record.component_properties != record.product_variant_ids[0].component_properties:
                record.product_variant_ids[0].write({'component_properties': record.component_properties})

    @api.depends('product_variant_ids.short_description')
    def _compute_short_description(self):
        for record in self:
            record.short_description = record.product_variant_ids[0].short_description

    def _inverse_short_description(self):
        for record in self:
            if record.product_variant_count == 1 and \
                    record.short_description and \
                    record.short_description != record.product_variant_ids[0].short_description:
                record.product_variant_ids[0].write({'short_description': record.short_description})

    def action_update_nextar_data(self):
        for record in self:
            for product_id in record.product_variant_ids:
                product_id.action_update_nextar_data()
