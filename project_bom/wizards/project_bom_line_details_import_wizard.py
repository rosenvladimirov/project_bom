# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import logging
import os
import string
from xml.etree import ElementTree as ET
from xxsubtype import bench

from odoo.tools import config
from ..libs.InteractiveHtmlBom.core.ibom import generate_bom, generate_file
from ..libs.InteractiveHtmlBom.ecad.fusion_eagle import FusionEagleParser
from ..libs.InteractiveHtmlBom.core.config import Config
from ..libs.InteractiveHtmlBom.version import version

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
    data_file_sch = fields.Binary(string='File sch')
    filename_sch = fields.Char(string='Filename sch')
    data_file_html = fields.Binary(string='File html')
    filename_html = fields.Char(string='Filename html')

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
        def rot(rot_string):
            if not rot_string:
                return False, False, 0.0
            return 'M' in rot_string, 'S' in rot_string, float(''.join(d for d in rot_string if d in string.digits + '.'))

        new_import_data = self.env['project.bom.line.details.import.data']
        root = ET.fromstring(base64.b64decode(self.data_file))
        board = root.find('drawing').find('board')
        plain = board.find('plain')
        elements = board.find('elements')
        signals = board.find('signals')

        data = {}
        for el in elements.iter('element'):
            populate = el.get('populate', '') != 'no'
            if not populate:
                continue
            libs = [lib for lib in board.find('libraries').findall('library')
                    if lib.attrib['name'] == el.attrib['library']]
            elr = rot(el.get('rot'))
            layer = 'B' if elr[0] else 'F'
            designator = el.get('name')

            elx = float(el.attrib['x'])
            ely = float(el.attrib['y'])

            if designator.startswith("R"):
                package = el.get('package', '').split('_')[0]
                package = "RC" + package[1:]
                value = el.get('value')
                if value.split('/')[0] == 'NC':
                    value = "_".join(value.split('/')[:-1]+['NC'])
                value = value.replace("/", "_").replace("-", "_")
                if value.upper() == "0R":
                    value = "0"
            elif designator.startswith("C"):
                package = el.get('package', '').split('_')[0]
                package = "CC" + package[1:]
                value = el.get('value', '').replace("/", "_").replace("-", "_").replace("F", "").replace('f', '')
                if value.find('.') != -1:
                    value = "_".join(map(lambda s: s.replace('.', s[-1])[:-1], value.split('_')))
            else:
                package = el.get('package', '')
                value = el.get('value')

            if value.startswith('TESTPAD') \
                    or value.startswith('TP_') \
                    or value.startswith('') == 'FIDUCIAL' \
                    or value == 'GND' \
                    or value.upper() == 'DNP':
                continue

            if not data.get(designator):
                data[designator] = {
                    "package": package,
                    "value": value,
                    "rot": elr,
                    "layer": layer,
                    "libs": libs,
                    "x": elx,
                    "y": ely,
                }

            for a in el.iter('attribute'):
                attribute = a.attrib
                if 'name' in attribute:
                    name = attribute['name'].lower()
                    # _logger.info(f"COMPONENT {attribute}")
                    if not data[designator].get("options"):
                        data[designator]['options'] = {}
                    if not data[designator]['options'].get(name):
                        data[designator]['options'][name] = {}
                    for k, v in attribute.items():
                        if k == 'name':
                            continue
                        data[designator]['options'][name].update({k.lower(): v})
                    # extra_fields[a.attrib['name']] = a.attrib['value']
        for designator, attribute in data.items():
            _logger.info(f"{designator}: {attribute}")
            if attribute.get('options') and attribute['options'].get('mecid', False):
                short_description = attribute['options']['MecID']
            else:
                short_description = f"{attribute.get('package')}_{attribute.get('value')}"

            if attribute.get('options') and attribute['options'].get('artid', False):
                default_code = attribute['options']['artid']
            else:
                default_code = ""

            if attribute.get('options') and attribute['options'].get('opt'):
                short_description_option = attribute['options']['opt'].get('value', '')
            else:
                short_description_option = ''

            new_import_data.create({
                'qty': 1.0,
                'designator': designator,
                'default_code': default_code,
                'description': f"package:{attribute.get('package')} value: {attribute.get('value')}",
                'short_description': short_description,
                'short_description_option': short_description_option,
                'manufacturer_part': attribute.get('options')
                                     and attribute['options'].get('manufacturer_part_number', '') and attribute['options']['manufacturer_part_number'].get('value') or ''
                                     or '',
                'x_coordinate': attribute.get('x', 0.0),
                'y_coordinate': attribute.get('y', 0.0),
                'theta': attribute.get('rot') and attribute['rot'][2] or 0.0,
                'import_id': self.id,
            })

    def _brd_update(self):
        if self.line_details:
            root = ET.fromstring(base64.b64decode(self.data_file))
            board = root.find('drawing').find('board')
            plain = board.find('plain')
            elements = board.find('elements')
            signals = board.find('signals')
            layers = root.find('drawing').find('layers')
            text_layer = ET.Element('layer', {'number': '1'})
            for layer in layers.iter():

                if layer.find('name').text == 'tValues':
                    text_layer = layer
                    break

            for line in self.line_details:
                if line.product_id:
                    element = elements.find('.//element[@value]')
                    if element[0].text == line.designator:
                        element.append(ET.Element('attribute', {
                            'name': 'ArtID',
                            'value': line.product_id.default_code,
                            'y': element.get('y'),
                            'x': element.get('x'),
                            'size': '1.778',
                            'layer': text_layer.get('number'),
                            'display': 'off'
                        }))
                        if line.product_id.short_description or line.product_id.product_tmpl_id.short_description:
                            element.append(ET.Element('attribute', {
                                'name': 'MecID',
                                'value': line.product_id.short_description or line.product_id.product_tmpl_id.short_description,
                                'y': element.get('y'),
                                'x': element.get('x'),
                                'size': '1.778',
                                'layer': text_layer.get('number'),
                                'display': 'off'
                            }))
            self.data_file = base64.b64encode(ET.tostring(root, encoding='utf-8', xml_declaration=True))

    def _sch_import(self):
        new_import_data = self.env['project.bom.line.details.import.data']
        sch_root = ET.fromstring(base64.b64decode(self.data_file))
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
                'bom_product_template_attribute_value_ids': [Command.set(line.possible_bom_product_template_attribute_value_ids.ids)],
                'semi_product_tmpl_id': self.semi_product_tmpl_id.id,
                'semi_product_id': self.semi_product_id.id,
            })

    def action_html(self):
        self.ensure_one()

        config_ibom = Config(version, config.rcfile)
        config_ibom.show_fields = ['MANUFACTURER_PART_NUMBER', 'OPT', 'MecID', 'ArtID']
        self._brd_update()

        parser = FusionEagleParser(
            False,
            config_ibom,
            _logger,
            contend=base64.b64decode(self.data_file)
        )
        pcbdata, components = parser.parse()
        if not pcbdata and not components:
            raise UserError('Parsing failed.')

        pcbdata["bom"] = generate_bom(components, config_ibom)
        pcbdata["ibom_version"] = config_ibom.version
        html = generate_file(pcbdata, config_ibom, _logger)
        self.data_file_html = base64.b64encode(html.encode('utf-8'))
        self.filename_html = 'ibom.html'
        return {
            'name': _('Import BOM Line Details'),
            'view_mode': 'form',
            'res_model': 'project.bom.line.details.import.wizard',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }

        # # build BOM
        # new_wizard = self.env['project.bom.interactive.bom'].create({
        #     'html': generate_file(pcbdata, config_ibom, _logger)
        # })
        #
        # view_id = self.env.ref('project_bom.view_project_bom_line_details_import_wizard_html_form')
        # return {
        #     'name': 'View BOM HTML',
        #     'res_model': new_wizard._name,
        #     'view_mode': 'form',
        #     'views': [[False, 'form']],
        #     'view_id': view_id.id,
        #     'type': 'ir.actions.act_window',
        #     'res_id': new_wizard.id,
        #     'target': 'new'
        # }

    def _validate_data(self):
        is_valid = True
        for line in self.line_details:
            line_valid = True
            error_message = []

            if line.qty % 1 != 0:
                error_message.append(_('Designator count does not match quantity.'))
                line_valid = False

            if line.default_code:
                found_products = self.env['product.product'].search([
                    ('default_code', '=', line.default_code)
                ])
                if not found_products:
                    if not line.short_description:
                        error_message.append(_('Technical description is required.'))
                        line_valid = False
                if found_products:
                    line.product_id = found_products[0].id
                    error_message.append(
                        _(f"{len(found_products) > 1 and 'To many products found with some technical description or default code' or ''}"))
            else:
                error_message.append(_('Internal reference is required.'))
                line_valid = False

            if line.short_description and not line.default_code:
                found_products = self.env['product.product'].search([
                    '|',
                    ('short_description', 'like', line.short_description.strip()),
                    ('product_tmpl_id.short_description', 'like', line.short_description.strip())
                ])
                if found_products:
                    line.product_id = found_products[0].id
                    if len(found_products) > 1:
                        error_message.append(
                            _(f"{'To many products found with some technical description or default code'}"))
                else:
                    error_message.append(_('Product not found. The technical description '
                                           'or default code are not matching any product.'))
                    line_valid = False

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
                possible_product_template_attribute_value_ids = line.possible_bom_product_template_attribute_value_ids.mapped('name')
                if line.short_description_option in possible_product_template_attribute_value_ids:
                    bom_product_template_attribute_value_ids = line.possible_bom_product_template_attribute_value_ids. \
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
