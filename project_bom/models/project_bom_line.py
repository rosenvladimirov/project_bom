# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _, Command
from odoo.models import NewId

_logger = logging.getLogger(__name__)


class ProjectMrpBomLine(models.Model):
    _name = 'project.mrp.bom.line'
    _description = 'Project bom lines'
    _order = "sequence, id"
    # _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'mrp.bom.line': 'bom_line_id'}

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    sequence = fields.Integer('Sequence',
                              default=1,
                              copy=False,
                              help="Gives the sequence order when displaying.")
    project_bom_id = fields.Many2one('project.mrp.bom',
                                     'Parent Project BOM',
                                     index=True,
                                     ondelete='cascade',
                                     required=True)
    display_type = fields.Selection(
        selection=[
            ('line_operation', "Operation"),
            ('line_note', "Note"),
        ],
        default=False)
    company_id = fields.Many2one('res.company',
                                 related='project_bom_id.company_id',
                                 store=True)
    bom_line_id = fields.Many2one('mrp.bom.line',
                                  'BOM Line',
                                  required=True,
                                  ondelete='restrict',
                                  copy=False)
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

    version_ids = fields.One2many('project.mrp.bom.line.version',
                                 'bom_line_id',
                                 'Versions',
                                  copy=False)
    project_product_id = fields.Many2one('product.product',
                                         'Component',
                                         required=True,
                                         check_company=True)
    project_product_uom_category_id = fields.Many2one(related='project_product_id.uom_id.category_id')
    project_product_uom_id = fields.Many2one(
        'uom.uom', 'Product Unit of Measure',
        default=_get_default_product_uom_id,
        required=True,
        help="Unit of Measure (Unit of Measure) is the unit of measurement for the inventory control",
        domain="[('category_id', '=', project_product_uom_category_id)]")
    name = fields.Char('Description', related="project_operation_id.name", readonly=False, store=True)

    project_workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    project_allowed_operation_ids = fields.Many2many('mrp.routing.workcenter',
                                             compute="_compute_project_allowed_operation_ids")

    project_product_qty = fields.Float('Quantity', default=1.0, digits='Product Unit of Measure', required=True)
    project_operation_id = fields.Many2one('mrp.routing.workcenter',
                                           'Consumed in Operation',
                                           check_company=True,
                                           domain="[('id', 'in', project_allowed_operation_ids)]",
                                           help="The operation where the components are consumed, "
                                                "or the finished products created.")
    approve = fields.Boolean('Approved')

    @api.depends('project_workcenter_id')
    def _compute_project_allowed_operation_ids(self):
        for record in self:
            project_allowed_operation_ids = self.env['mrp.routing.workcenter'].search([
                ('workcenter_id', '=', record.project_workcenter_id.id)
            ])
            record.project_allowed_operation_ids = [Command.set(project_allowed_operation_ids)]

    def action_approve(self, product_id):
        for record in self:
            if isinstance(record.id, NewId):
                break
            project_bom_id = record.project_bom_id
            version = self.env['project.mrp.bom.line.version'].search([
                ('bom_line_id', '=', record.id), ('version', '=', project_bom_id.version)
            ])
            if record.approve:
                if record.project_product_id.id != product_id:
                    change_product_id = record.project_bom_id.project_bom_line_ids.\
                        filtered(lambda r: r.project_product_id == record.project_product_id
                                           and r.project_operation_id == record.project_operation_id)
                    if change_product_id:
                        change_product_id.project_product_qty = record.project_product_qty
                    else:
                        bom_id = record.bom_line_id.bom_id
                        change_bom_product_id = bom_id.bom_line_ids.\
                            filtered(lambda r: r.product_id == record.project_product_id)
                        if not change_bom_product_id:
                            change_bom_product_id = self.env['project.mrp.bom.line'].create({
                                'bom_id': bom_id.id,
                                'product_id': record.project_product_id.id,
                                'product_uom_id': record.project_product_uom_id.id,
                                'product_qty': record.project_product_qty,
                            })
                            bom_id.bom_line_ids |= change_bom_product_id
                        record.project_bom_id.project_bom_line_ids |= record.copy(default={
                            'project_bom_id': record.project_bom_id.id,
                            'bom_line_id': change_bom_product_id.id,
                        })
                else:
                    record.bom_line_id.product_id = record.project_product_id
                    record.bom_line_id.product_uom_id = record.project_product_uom_id
                    record.bom_line_id.product_qty = record.project_product_qty
                    if not version:
                        record.version_ids.create({
                            'bom_line_id': record.id,
                            'version': project_bom_id.version,
                            'product_id': record.project_product_id.id,
                            'product_uom_id': record.project_product_uom_id.id,
                            'product_qty': record.project_product_qty,
                        })
            elif not record.approve and version:
                record.bom_line_id.product_id = version.product_id
                record.bom_line_id.product_uom_id = version.product_uom_id
                record.bom_line_id.product_qty = version.product_qty
            # record.project_bom_id

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for project_line_id, vals in zip(res, vals_list):
            project_line_id.project_bom_id.action_update_groups(project_line_id, vals)
        return res
