# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import logging
from xml.etree import ElementTree as ET

from odoo import models, fields, _, Command
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

HEADER_FIELDS = {
    'qty': 'qty',
    'ArtID': 'default_code',
    'MecID': 'short_description',
    'description': 'description',
    'manufacturer': False,
    'MPN': False,
    'Semi product': False,
    'opt': 'short_description_option',
    'mounted': False,
    'package': False,
    'RefDes': 'designator',
    'notes': False,
    'ss': False,
    'side': False,
    'type': 'type',
}


class ProjectBomLineImportWizard(models.TransientModel):
    _name = 'project.bom.line.details.import.wizard'
    _description = 'Import BOM Line Details'

    data_file = fields.Binary(string='File')
    filename = fields.Char(string='Filename')
    validated = fields.Boolean(string='Validated', default=False)
    line_details = fields.One2many('project.bom.line.details.import.data',
                                   'import_id',
                                   string='Line Details')
    project_bom_id = fields.Many2one('project.mrp.bom', string='Project BOM')
    product_tmpl_id = fields.Many2one('product.template', related="project_bom_id.product_tmpl_id")
    product_id = fields.Many2one('product.product', related="project_bom_id.product_id")
    semi_product_tmpl_id = fields.Many2one('product.template',
                                           string='Semi Product Template')
    semi_product_id = fields.Many2one('product.product',
                                      string='Semi Product')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get('project_bom_id') and self._context.get('active_model') == 'project.mrp.bom':
            res['project_bom_id'] = self._context.get('active_id')
        if res.get('project_bom_id'):
            project_bom_id = self.env['project.mrp.bom'].browse(res['project_bom_id'])
            res['product_tmpl_id'] = project_bom_id.product_tmpl_id.id
            res['product_id'] = project_bom_id.product_id.id
        return res

    def onchange_semi_product_tmpl_id(self):
        if self.semi_product_tmpl_id:
            self._validate_data()
        return {}

    def _base_internal_import(self, mimetype):
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
        import_header = []
        for header in result_parse['headers']:
            _logger.info("Header: %s", header)
            import_header.append(HEADER_FIELDS.get(header, False))
        # ['qty', 'default_code', 'short_description', 'description', False, False,
        #  'short_description_option', False, False, 'designator', False, False, False, False]
        _logger.info("Import Header: %s", import_header)
        if not import_header:
            raise UserError('No header fields found. Please make sure the header '
                            'row is not hidden and all columns are populated.')
        results = import_wizard.execute_import(import_header, [], {**opts})

        if results.get('messages'):
            message = ''
            for msg in results['messages']:
                message += msg['message'] + '\n'
            raise UserError(message)

        new_import_data = self.env['project.bom.line.details.import.data']
        import_data = self.env['project.bom.line.details.import.data'].browse(results['ids'])
        # Check for designators and add import_id
        for import_line in import_data:
            designator_import_lines = import_line.designator and import_line.designator.split(',') or []
            for designator in designator_import_lines:
                new_import_data.create({
                    'qty': import_line.qty / len(designator_import_lines),
                    'default_code': import_line.default_code,
                    'short_description': import_line.short_description,
                    'description': import_line.description,
                    'short_description_option': import_line.short_description_option,
                    'designator': designator,
                    'import_id': self.id
                })
            if not designator_import_lines:
                new_import_data.create({
                    'qty': import_line.qty,
                    'default_code': import_line.default_code,
                    'short_description': import_line.short_description,
                    'description': import_line.description,
                    'short_description_option': import_line.short_description_option,
                    'import_id': self.id
                })
        import_data.unlink()

    def _brd_import(self):
        new_import_data = self.env['project.bom.line.details.import.data']
        brdxml = ET.parse(base64.b64decode(self.data_file))
        root = brdxml.getroot()
        board = root.find('drawing').find('board')
        plain = board.find('plain')
        elements = board.find('elements')
        signals = board.find('signals')

        for el in elements.iter('element'):
            populate = el.get('populate') != 'no'
            for a in el.iter('attribute'):
                if 'value' in a.attrib and a.attrib['value'].upper() != 'DNP':
                    part_attrib = a.attrib
                    # extra_fields[a.attrib['name']] = a.attrib['value']
                    short_description = f"{part_attrib.get('package')}_{part_attrib.get('value')}"
                    product_id = self.env['product.product'].search([
                        ('short_description', 'ilike', short_description)
                    ], limit=1)
                    new_import_data.create({
                        'qty': 1.0,
                        'designator': part_attrib.get('name'),
                        'default_code': product_id and product_id.default_code or '',
                        'description': f"library: {part_attrib.get('library')} device set:{part_attrib.get('deviceset')}",
                        'product_id': product_id and product_id.id or False,
                        'short_description': short_description,
                        'import_id': self.id
                    })

    def _sch_import(self):
        new_import_data = self.env['project.bom.line.details.import.data']
        sch_tree = ET.parse(base64.b64decode(self.data_file))
        sch_root = sch_tree.getroot()
        drawing = sch_root.find("drawing")
        # settings = drawing.find("settings").findall("setting")
        # grid = drawing.find("grid")
        # layers = drawing.find("layers").findall("layer")
        schematic = drawing.find("schematic")
        # libraries = schematic.find("libraries").findall("library")
        parts = schematic.find("parts").findall("part")
        # sheets = schematic.find("sheets").findall("sheet")

        for part in parts:
            _logger.info(f"{part.attrib}")
            part_attrib = part.attrib
            if not part_attrib.get('device'):
                continue
            short_description = f"{part_attrib.get('device')}_{part_attrib.get('value')}"
            product_id = self.env['product.product'].search([
                ('short_description', 'ilike', short_description)
            ], limit=1)
            new_import_data.create({
                'qty': 1.0,
                'designator': part_attrib.get('name'),
                'default_code': product_id and product_id.default_code or '',
                'description': f"library: {part_attrib.get('library')} device set:{part_attrib.get('deviceset')}",
                'product_id': product_id and product_id.id or False,
                'short_description': short_description,
                'import_id': self.id
            })

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
            elif file_extension == 'sch':
                mimetype = 'application/x-schematics'
            elif file_extension == 'brd':
                mimetype = 'application/eagle+xml'
            else:
                raise UserError('Unsupported file format. Please upload a CSV, XLS, or XLSX file.')

            if self.line_details:
                self.line_details.unlink()

            if mimetype in ['text/csv',
                            'application/vnd.ms-excel',
                            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            'application/vnd.oasis.opendocument.spreadsheet'
                            ]:
                self._base_internal_import(mimetype)

            elif mimetype == 'application/x-schematics':
                self._sch_import()
            elif mimetype == 'application/eagle+xml':
                self._brd_import()

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
        for line in self.line_details:
            self.env['project.bom.line.details'].create({
                'project_bom_id': self.project_bom_id.id,
                'product_id': line.product_id.id,
                'product_qty': line.qty,
                'designator': line.designator,
                'hw_option': line.hw_option.id,
                'bom_product_template_attribute_value_ids': [Command.set(line.possible_product_template_attribute_value_ids.ids)],
                'semi_product_tmpl_id': self.semi_product_tmpl_id.id,
                'semi_product_id': self.semi_product_id.id,
            })

    def _validate_data(self):
        is_valid = True
        for line in self.line_details:
            line_valid = True
            error_message = []

            if line.qty % 1 != 0:
                error_message.append(_('Designator count does not match quantity.'))
                line_valid = False

            if not line.default_code:
                error_message.append(_('Internal reference is required.'))
                line_valid = False
            else:
                found_products = self.env['product.product'].search([
                    ('default_code', '=', line.default_code)
                ])
                if not found_products:
                    if not line.short_description:
                        error_message.append(_('Technical description is required.'))
                        line_valid = False
                    else:
                        found_products = self.env['product.product'].search([
                            ('short_description', '=', line.short_description)
                        ])
                        if not found_products:
                            error_message.append(_('Product not found. The technical description '
                                                   'or default code are not matching any product.'))
                            line_valid = False
                if found_products:
                    line.product_id = found_products[0].id
                    error_message.append(
                        _(f"{len(found_products) > 1 and 'To many products found with some technical description or default code' or ''}"))
            if line.short_description_option and not line.short_description_option != '_' and line.type == 'kit':
                found_products = self.env['product.product'].search([
                    ('short_description', '=', line.short_description_option),
                ])
                if found_products:
                    line.hw_option = found_products[0].id
                    error_message.append(
                        _(f"{len(found_products) > 1 and 'To many kits found with some hw option description' or ''}"))
                else:
                    error_message.append(_('Product not found. The hw option description '
                                           'are not matching any kit product.'))
                    line_valid = False
            elif line.short_description_option and not line.short_description_option != '_' and line.type == 'normal':
                possible_product_template_attribute_value_ids = line.possible_product_template_attribute_value_ids.mapped('name')
                if line.short_description_option in possible_product_template_attribute_value_ids:
                    bom_product_template_attribute_value_ids = line.possible_product_template_attribute_value_ids. \
                        filtered(lambda r: r.name == line.short_description_option)
                    line.bom_product_template_attribute_value_ids = \
                        [Command.set(bom_product_template_attribute_value_ids.ids)]
                else:
                    error_message.append(_('Attribute value not found. The hw option is wrong'))
                    line_valid = False

            line.write({
                'is_valid': line_valid,
                'error_message': error_message and '\n'.join(error_message) or "",
            })
            if not line_valid:
                is_valid = False

        self.validated = is_valid
