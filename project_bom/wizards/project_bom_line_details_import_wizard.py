# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo import models, fields, _
from odoo.exceptions import UserError


class ProjectBomLineImportWizard(models.TransientModel):
    _name = 'project.bom.line.details.import.wizard'
    _description = 'Import BOM Line Details'

    data_file = fields.Binary(string='File')
    filename = fields.Char(string='Filename')
    not_validated = fields.Boolean(string='Validated', default=True)
    line_details = fields.One2many('project.bom.line.details.import.data',
                                   'import_id',
                                   string='Line Details')
    project_bom_id = fields.Many2one('project.mrp.bom', string='Project BOM')
    product_tmpl_id = fields.Many2one('product.template', related="project_bom_id.product_tmpl_id")
    product_id = fields.Many2one('product.product', related="project_bom_id.product_id")

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get('project_bom_id') and self._context.get('active_model') == 'project.mrp.bom':
            res['project_bom_id'] = self._context.get('active_id')
        if res.get('project_bom_id'):
            project_bom_id = self.env['project.mrp.bom'].browse(res['project_bom_id'])
            res['product_tmpl_id'] = project_bom_id.product_tmpl_id.id
            res['product_id'] = project_bom_id.product_id.id
        return res

    def action_upload(self):
        self.ensure_one()

        if self.data_file:
            file_extension = self.filename.split('.')[-1]
            if file_extension == 'csv':
                mimetype = 'text/csv'
            elif file_extension == 'xls':
                mimetype = 'application/vnd.ms-excel'
            elif file_extension == 'xlsx':
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif file_extension == 'ods':
                mimetype = 'application/vnd.oasis.opendocument.spreadsheet'
            else:
                raise UserError('Unsupported file format. Please upload a CSV, XLS, or XLSX file.')

            if self.line_details:
                self.line_details.unlink()

            import_wizard = self.env['base_import.import'].create({
                'res_model': 'project.bom.line.details.import.data',
                'file': base64.b64decode(self.data_file),
                'file_type': mimetype
            })

            opts = {
                'date_format': '',
                'datetime_format': '',
                'quoting': '"',
                'separator': ',',
                'float_decimal_separator': '.',
                'float_thousand_separator': ',',
                'has_headers': True
            }

            result_parse = import_wizard.parse_preview({**opts})

            if result_parse.get('error'):
                raise UserError(result_parse['error'])

            opts = result_parse['options']
            results = import_wizard.execute_import(
                ['qty', 'default_code', 'short_description', 'description', False, False, False, False, False,
                 'designator', False, False, False, False],
                [],
                {**opts}
            )

            if results.get('messages'):
                message = ''
                for msg in results['messages']:
                    message += msg['message'] + '\n'
                raise UserError(message)

            new_import_data = self.env['project.bom.line.details.import.data']
            import_data = self.env['project.bom.line.details.import.data'].browse(results['ids'])
            # Check for designators and add import_id
            for import_line in import_data:
                designator_import_lines = import_line.designator.split(',')
                for designator in designator_import_lines:
                    new_import_data.create({
                        'qty': import_line.qty / len(designator_import_lines),
                        'default_code': import_line.default_code,
                        'short_description': import_line.short_description,
                        'description': import_line.description,
                        'designator': designator,
                        'import_id': self.id
                    })
                if not designator_import_lines:
                    new_import_data.create({
                        'qty': import_line.qty,
                        'default_code': import_line.default_code,
                        'short_description': import_line.short_description,
                        'description': import_line.description,
                        'import_id': self.id
                    })
            import_data.unlink()
        self._validate_data()
        action = self.env.ref('project_bom.action_custom_import_wizard', raise_if_not_found=False)

        if action:
            result = action.read()[0]
            result['res_id'] = self.id
            return result

        return {
            'name': _('Import BOM Line Details'),
            'view_mode': 'form',
            'res_model': 'project.bom.line.details.import.wizard',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }

    def action_import(self):
        # self._validate_data()
        if self.not_validated:
            raise UserError('Please fix validation errors!')

        for line in self.line_details:
            if not line.product_id:
                raise UserError('Product not found. The technical description or default code are not matching any product.')
            self.env['project.bom.line.details'].create({
                'project_bom_id': self.project_bom_id.id,
                'product_id': line.product_id.id,
                'designator': line.designator,
                'description': line.description,
                'short_description': line.short_description,
            })

    def _validate_data(self):
        not_validated = False
        for line in self.line_details:
            lines_valid = True
            error_message = []

            designators = line.designator.split(',')

            if len(designators) != line.qty:
                error_message.append(_('Designator count does not match quantity.'))
                lines_valid = False

            if not line.default_code:
                error_message.append(_('Internal reference is required.'))
                lines_valid = False
            else:
                found_products = self.env['product.product'].search([
                    ('default_code', '=', line.default_code)
                ])
                if not found_products:
                    if not line.short_description:
                        error_message.append(_('Technical description is required.'))
                        lines_valid = False
                    else:
                        found_products = self.env['product.product'].search([
                            ('short_description', '=', line.short_description)
                        ])
                        if not found_products:
                            error_message.append(_('Product not found. The technical description '
                                                   'or default code are not matching any product.'))
                            lines_valid = False
                if found_products:
                    line.product_id = found_products[0].id
                    error_message.append(_(f"{len(found_products) > 1 and 'To many products found with some technical description or default code' or ''}"))

            line.write({
                'not_validated': lines_valid,
                'error_message': error_message and '\n'.join(error_message) or "",
            })
            if not not_validated and not lines_valid:
                not_validated = True

        self.not_validated = not_validated
