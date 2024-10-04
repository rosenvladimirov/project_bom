# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _, Command

_logger = logging.getLogger(__name__)

NEXAR_PART_ATTRIBUTES = """
query specAttributes(
    $mpn: String!
    $limit: Int
){
  supSearchMpn(
    q: $mpn
    limit: $limit
    ) {
    hits
    results {
      part {
        id
        name
        mpn
        specs {
          attribute {
            name
            id
            shortname
          }
          displayValue
        }      
      }
    }
  }
}
"""
NEXAR_ALTERNATIVE_PART = """query findAlternativeParts(
    $mpn: String!
    $limit: Int
) {
  supSearchMpn(
    q: $mpn
    limit: $limit
    ) {
    hits
    results {
      part {
        similarParts {
          name
          octopartUrl
          mpn
        }
      }
    }
  }
}"""


class ProductProduct(models.Model):
    _inherit = "product.product"

    direct_standard_price = fields.Float('Cost', company_dependent=True)
    # CAD additional information
    short_description = fields.Char('Technical Description', size=40)
    component_type_id = fields.Many2one('component.definition.properties', 'Definition properties',)
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

    @api.onchange('short_description')
    def _onchange_short_description(self):
        for record in self:
            if record.short_description \
                    and record.product_tmpl_id.short_description != record.short_description \
                    and record.product_tmpl_id.product_variant_count == 1:
                record.product_tmpl_id.short_description = record.short_description

    @api.onchange('component_type_id')
    def _onchange_component_type_id(self):
        for record in self:
            if record.component_type_id \
                    and record.product_tmpl_id.component_type_id != record.component_type_id \
                    and record.product_tmpl_id.product_variant_count == 1:
                record.product_tmpl_id.component_type_id = record.component_type_id

    @api.model_create_multi
    def create(self, vals_list):
        if not self._context.get('block_properties', False):
            for vals in vals_list:
                if vals.get('component_properties', False) and vals.get('product_tmpl_id', False):
                    product_tmpl_id = self.env['product.template'].browse(vals['product_tmpl_id'])
                    if product_tmpl_id.product_variant_count == 1:
                        product_tmpl_id.with_context(**dict(self._context, block_properties=True)).write({
                            'component_properties': vals['component_properties'],
                        })
        return super().create(vals_list)

    def write(self, vals):
        if not self._context.get('block_properties', False) and vals.get('component_properties', False):
            product_tmpl_id = self.mapped('product_tmpl_id')
            if product_tmpl_id.product_variant_count == 1:
                product_tmpl_id.with_context(**dict(self._context, block_properties=True)).write({
                    'component_properties': vals['component_properties']
                })
        return super().write(vals)

    def _get_product_properties(self, key, value):
        current_component_properties = {}
        all_properties = self.read(['component_properties'])[0]['component_properties']
        for curr in list(filter(lambda x: x['string'] == key, all_properties)):
            current_component_properties.update({
                curr.get('name'): value
            })
        return current_component_properties

    def action_update_nextar_data(self):
        for record in self:
            all_properties = self.read(['component_properties'])[0]['component_properties']
            component_properties = list(filter(lambda x: x['string'] == 'mpn', all_properties))
            current_component_properties = record.component_properties or {}
            for component_properties in component_properties:
                if component_properties.get('string', '') == 'mpn' and component_properties.get('value', False):
                    mpn = component_properties['value']
                    query = NEXAR_PART_ATTRIBUTES
                    status, response, ask_time = self.env.user._do_request('', json={
                        "query": query,
                        "variables": {
                            'mpn': mpn,
                            'limit': 1
                        }
                    })
                    data = response.get('data')
                    for result in data.get("supSearchMpn",{}).get("results",{}):
                        for part in result.get("part",{}).get("specs",{}):
                            if part.get('attribute').get('name') == 'mpm':
                                continue
                            current_component_properties.update(
                                record._get_product_properties(part.get('attribute').get('name'), part.get('displayValue'))
                            )
                            # for curr in list(filter(lambda x: x['string'] == part.get('attribute').get('name'), all_properties)):
                            #     current_component_properties.update({
                            #         curr.get('name'): part.get('displayValue')
                            #     })
                    record.component_properties = current_component_properties
