import base64

from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.modules.loading import load_data


class ProjectBomLineImportWizard(models.TransientModel):
    _name = 'project.bom.line.details.import.wizard'
    _description = 'Import BOM Line Details'

    data_file = fields.Binary(string='File')
    filename = fields.Char(string='Filename')

    not_validated = fields.Boolean(string='Validated', default=True)

    line_details = fields.One2many('project.bom.line.details.import.data', 'import_id', string='Line Details')

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

            import_data = self.env['project.bom.line.details.import.data'].browse(results['ids'])
            import_data.write({'import_id': self.id})

        self._validate_data();

        return {
            'name': _('Import BOM Line Details'),
            'view_mode': 'form',
            'res_model': 'project.bom.line.details.import.wizard',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }

    def action_import(self):
        if self.not_validated:
            raise UserError('Please fix validation errors!')

        for line in self.line_details:
            designators = line.designator.split(',')
            found_products = self.env['product.product'].search([('default_code', '=', line.default_code)])
            if not found_products:
                found_products = self.env['product.product'].search([('short_description', '=', line.short_description)])

            if not found_products:
                raise UserError('Product not found. The technical description or default code are not matching any product.')

            for designator in designators:
                self.env['project.mrp.bom.line.details'].create({
                    'project_bom_id': self.env.context.get('project_bom_id'),
                    'product_id': found_products[0].id,
                    'designator': designator
                })


    def _validate_data(self):
        lines_valid = True
        for line in self.line_details:
            designators = line.designator.split(',')
            if len(designators) != line.qty:
                line.error_message = 'Designator count does not match quantity.'
                lines_valid = False

            if not line.default_code:
                line.error_message = 'Internal reference is required.'
                lines_valid = False
            else:
                found_products = self.env['product.product']. \
                    search([('default_code', '=', line.default_code)])
                if not found_products:
                    if not line.short_description:
                        line.error_message = 'Technical description is required.'
                        lines_valid = False
                    else:
                        found_products = self.env['product.product']. \
                            search([('short_description', '=', line.short_description)])
                        if not found_products:
                            line.error_message = \
                                'Product not found. The technical description or default code are not matching any product.'
                            lines_valid = False
        if lines_valid:
            self.not_validated = False