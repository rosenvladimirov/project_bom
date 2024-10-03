# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import logging
import string
from fileinput import filename
from xml.etree import ElementTree as ET

from odoo.tools import config
from ..libs.InteractiveHtmlBom.core.ibom import generate_bom, generate_file
from ..libs.InteractiveHtmlBom.ecad.fusion_eagle import FusionEagleParser
from ..libs.InteractiveHtmlBom.core.config import Config
from ..libs.InteractiveHtmlBom.version import version

from odoo import models, fields, _, Command, api
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

MIMETYPES = {
    'csv': 'text/csv',
    'txt': 'text/plain',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
    'sch': 'application/x-schematics',
    'brd': 'application/eagle+xml',
}


class ProjectBomLineImportWizard(models.TransientModel):
    _name = 'project.bom.line.details.import.wizard'
    _description = 'Import BOM Line Details'

    data_file = fields.Binary(string='File')
    filename = fields.Char(string='Filename')
    filename_mimetype = fields.Char(string='Filename Ext')

    data_file_sch = fields.Binary(string='File sch')
    filename_sch = fields.Char(string='Filename sch')

    # data_file_html = fields.Binary(string='File html')
    # filename_html = fields.Char(string='Filename html')

    # data_file_txt = fields.Binary(string='File txt')
    # filename_txt = fields.Char(string='Filename txt')

    # data_file_external = fields.Many2many('project.bom.line.details.import.data.files',
    #                                       relation='data_files_import_wizard_rel',
    #                                       string='PnP Files')
    data_file_external = fields.Many2many('ir.attachment',
                                          relation='ir_attachment_import_wizard_rel',
                                          string='External Files')

    panel_rotation = fields.Selection([
        ('0', _('0 degrees')),
        ('90', _('90 degrees')),
        ('180', _('180 degrees')),
        ('270', _('270 degrees')),
    ], string='Panel Rotation', default='0')

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
    comments = fields.Char('Description')

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
        if self.semi_product_tmpl_id or self.semi_product_id:
            self._validate_data()
        return {}

    def _base_internal_import(self, mimetype, data_file):
        current_data = self.line_details
        import_wizard = self.env['base_import.import'].create({
            'res_model': 'project.bom.line.details.import.data',
            'file': base64.b64decode(data_file),
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
            # _logger.info("Header: %s", header)
            import_header.append(HEADER_FIELDS.get(header, False))
        # ['qty', 'default_code', 'short_description', 'description', False, False,
        #  'short_description_option', False, False, 'designator', False, False, False, False]
        # _logger.info("Import Header: %s", import_header)
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
            short_description_option = import_line.short_description_option != '_' and import_line.short_description_option or False
            for designator in designator_import_lines:
                current_line = current_data.filtered(lambda r: r.designator.strip() == designator.strip())
                if current_line:
                    current_line.write({
                        'default_code': import_line.default_code,
                        'short_description': import_line.short_description,
                        'description': import_line.description,
                        'short_description_option': short_description_option,
                    })
                else:
                    new_import_data.create({
                        'qty': import_line.qty / len(designator_import_lines),
                        'default_code': import_line.default_code,
                        'short_description': import_line.short_description,
                        'description': import_line.description,
                        'short_description_option': short_description_option,
                        'designator': designator.strip(),
                        'import_id': self.id
                    })
            if not designator_import_lines:
                current_line = current_data.filtered(lambda r: r.designator.strip() == designator.strip())
                if current_line:
                    current_line.write({
                        'default_code': import_line.default_code,
                        'short_description': import_line.short_description,
                        'description': import_line.description,
                        'short_description_option': short_description_option,
                    })
                else:
                    new_import_data.create({
                        'qty': import_line.qty,
                        'default_code': import_line.default_code,
                        'short_description': import_line.short_description,
                        'description': import_line.description,
                        'short_description_option': short_description_option,
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

        fiducial = {}
        x_coordinate_fiducial_1 = y_coordinate_fiducial_1 = 0.0
        for el in elements.iter('element'):
            if el.get('name').startswith('FID'):
                designator = el.get('name')
                elr = rot(el.get('rot'))
                layer = 'B' if elr[0] else 'F'
                if not fiducial.get(designator):
                    fiducial[designator] = {}
                fiducial[designator].update({
                    'x_coordinate_fiducial': float(el.get('x')),
                    'y_coordinate_fiducial': float(el.get('y')),
                    'rot': elr[2],
                    'layer': layer,
                })

        if fiducial.get('FID1'):
            x_coordinate_fiducial_1 = fiducial['FID1']['x_coordinate_fiducial']
            y_coordinate_fiducial_1 = fiducial['FID1']['y_coordinate_fiducial']

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
            value = el.get('value')
            merge = True

            if designator.startswith("R"):
                package = el.get('package', '').split('_')[0]
                if package:
                    package = "R" + "".join(filter(str.isdigit, package))
                package = "RC" + package[1:]
                if value.split('/')[0] == 'NC':
                    value = "_".join(value.split('/')[:-1]+['NC'])
                value = value.replace("/", "_").replace("-", "_").replace('R', '').replace('r', '')
                if value.find('.') != -1:
                    value = "_".join(map(lambda s: s.replace('.', s[-1])[:-1], value.split('_')))
            elif designator.startswith("C") or designator.startswith("E_C"):
                package = el.get('package', '').split('_')[0]
                if package:
                    package = "C" + "".join(filter(str.isdigit, package))
                package = "CC" + package[1:]
                value = value.replace("/", "_").replace("-", "_").replace("F", "").replace('f', '')
                if value.find('.') != -1:
                    value = "_".join(map(lambda s: s.replace('.', s[-1])[:-1], value.split('_')))
            elif designator.startswith("L"):
                package = el.get('package', '').split('_')[0]
                if package:
                    package = "L" + "".join(filter(str.isdigit, package))
                package = "FC" + package[1:]
                value = value.replace("/", "_").replace("-", "_").replace("H", "").replace('h', '')
                if value.find('.') != -1:
                    value = "_".join(map(lambda s: s.replace('.', s[-1])[:-1], value.split('_')))
            else:
                package = el.get('package', '')
                value = el.get('value')
                merge = False

            if value.startswith('TESTPAD') \
                    or value.startswith('TP_') \
                    or value.upper() == 'GND' \
                    or value.upper() == 'DNP' \
                    or value.upper() == 'FIDUCIAL':
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
                    "x_fiducial_1": elx - x_coordinate_fiducial_1,
                    "y_fiducial_1": ely - y_coordinate_fiducial_1,
                    "merge_package_value": merge,
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
            if attribute.get('merge_package_value', False):
                short_description = f"{attribute.get('package')}_{attribute.get('value')}"
            else:
                short_description = f"{attribute.get('value')}"

            if attribute.get('options') and attribute['options'].get('mecid', False):
                short_description = attribute['options']['mecid'].get('value', False)

            if attribute.get('options') and attribute['options'].get('artid', False):
                default_code = attribute['options']['artid'].get('value', False)
            else:
                default_code = False

            if attribute.get('options') and attribute['options'].get('opt'):
                short_description_option = attribute['options']['opt'].get('value', False)
            else:
                short_description_option = False

            theta = attribute.get('rot') and attribute['rot'][2] or 0.0
            theta_txt = theta + float(self.panel_rotation)
            value = {
                'qty': 1.0,
                'designator': designator,
                'default_code': default_code,
                # 'description': f"package:{attribute.get('package')} value: {attribute.get('value')}",
                'short_description': short_description,
                'short_description_option': short_description_option,
                'short_description_semi_product': attribute.get('layer', ''),
                'manufacturer_part': attribute.get('options')
                                     and attribute['options'].get('manufacturer_part_number', '') and
                                     attribute['options']['manufacturer_part_number'].get('value') or ''
                                     or '',
                'x_coordinate': attribute.get('x', 0.0),
                'y_coordinate': attribute.get('y', 0.0),
                'x_coordinate_fiducial_1': attribute.get('x_fiducial_1', 0.0),
                'y_coordinate_fiducial_1': attribute.get('y_fiducial_1', 0.0),
                'theta': theta,
                'theta_txt': theta_txt >= 360.0 and theta_txt - 360.0 or theta_txt,
                'import_id': self.id,
            }
            # _logger.info(f"{value}")
            new_import_data.create(value)

    def _brd_update(self):
        def rot(rot_string):
            if not rot_string:
                return False, False, 0.0
            return 'M' in rot_string, 'S' in rot_string, float(''.join(d for d in rot_string if d in string.digits + '.'))

        if self.line_details:
            root = ET.fromstring(base64.b64decode(self.data_file))
            board = root.find('drawing').find('board')
            plain = board.find('plain')
            elements = board.find('elements')
            signals = board.find('signals')
            layers = root.find('drawing').find('layers')
            text_layer = ET.Element('layer', {'number': '1'})
            for layer in layers.iter('layer'):
                # _logger.info(f"layer: {layer.attrib}")
                if layer.attrib.get('name') == 'tValues':
                    text_layer = layer
                    break

            for line in self.line_details.sorted(lambda r: r.designator):
                # _logger.info(f"LINE {line.designator} - {line.product_id and line.product_id.name}")
                for el in elements.iter('element'):
                    element_attrib = el.attrib
                    # _logger.info(f"element: {element_attrib}")
                    if element_attrib['name'] == line.designator:
                        value = element_attrib.get('value')
                        elr = rot(element_attrib.get('rot'))
                        theta_txt = elr[2] + 180
                        if theta_txt >= 360:
                            theta_txt -= 360
                        if element_attrib.get('rot') and theta_txt == line.theta_txt:
                            _logger.info(f"theta {line.designator}: {theta_txt} != {elr[2]}")
                            if elr[2] % 1 == 0:
                                theta_txt = f"{theta_txt:.0f}"
                                theta = f"{elr[2]:.0f}"
                            else:
                                theta_txt = f"{theta_txt:.3f}"
                                theta = f"{elr[2]:.3f}"
                            el.set('rot', f"{element_attrib['rot'].replace(theta, theta_txt)}")
                        if value.strip() in ['DNP', 'NC']:
                            el.set('populate', 'no')
                        else:
                            el.set('populate', 'yes')

                        el.append(ET.Element('attribute', {
                            'name': 'theta',
                            'value': "%.2f" % line.theta,
                            'y': element_attrib.get('y'),
                            'x': element_attrib.get('x'),
                            'size': '1.778',
                            'layer': text_layer.get('number'),
                            'display': 'off'
                        }))
                        el.append(ET.Element('attribute', {
                            'name': 'xFid1',
                            'value': "%.3f" % line.x_coordinate_fiducial_1,
                            'y': element_attrib.get('y'),
                            'x': element_attrib.get('x'),
                            'size': '1.778',
                            'layer': text_layer.get('number'),
                            'display': 'off'
                        }))
                        el.append(ET.Element('attribute', {
                            'name': 'yFid1',
                            'value': "%.3f" % line.y_coordinate_fiducial_1,
                            'y': element_attrib.get('y'),
                            'x': element_attrib.get('x'),
                            'size': '1.778',
                            'layer': text_layer.get('number'),
                            'display': 'off'
                        }))
                        if line.product_id.default_code or line.product_id.product_tmpl_id.default_code:
                            el.append(ET.Element('attribute', {
                                'name': 'ArtID',
                                'value': line.product_id.default_code or line.product_id.product_tmpl_id.default_code,
                                'y': element_attrib.get('y'),
                                'x': element_attrib.get('x'),
                                'size': '1.778',
                                'layer': text_layer.get('number'),
                                'display': 'off'
                            }))
                        if line.product_id.short_description or line.product_id.product_tmpl_id.short_description:
                            el.append(ET.Element('attribute', {
                                'name': 'MecID',
                                'value': line.product_id.short_description or line.product_id.product_tmpl_id.short_description,
                                'y': element_attrib.get('y'),
                                'x': element_attrib.get('x'),
                                'size': '1.778',
                                'layer': text_layer.get('number'),
                                'display': 'off'
                            }))
                        if line.product_id.component_properties or line.product_id.product_tmpl_id.product_properties:
                            for component_properties in [line.product_id.component_properties, line.product_id.product_tmpl_id.product_properties]:
                                if component_properties:
                                    for key, properties in component_properties.items():
                                        # _logger.info(f"component_properties: {key}, {properties}")
                                        if properties:
                                            el.append(ET.Element('attribute', {
                                                'name': key,
                                                'value': str(properties),
                                                'y': element_attrib.get('y'),
                                                'x': element_attrib.get('x'),
                                                'size': '1.778',
                                                'layer': text_layer.get('number'),
                                                'display': 'off'
                                            }))
                        # _logger.info(f"element_attrib: {el.attrib}")
                        break

            self.data_file = base64.b64encode(ET.tostring(root, encoding='utf-8', xml_declaration=True))

    def _sch_import(self):
        current_data = self.line_details
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
            # _logger.info(f"{part.attrib}")
            part_attrib = part.attrib
            if not part_attrib.get('device'):
                continue
            designator = part_attrib.get('name')
            current_line = current_data.filtered(lambda r: r.designator.strip() == designator.strip())
            if not current_line:
                short_description = f"{part_attrib.get('device')}_{part_attrib.get('value')}"
                product_id = self.env['product.product'].search([
                    ('short_description', 'ilike', short_description)
                ], limit=1)
                new_import_data.create({
                    'qty': 1.0,
                    'designator': designator,
                    'default_code': product_id and product_id.default_code or '',
                    'description': f"library: {part_attrib.get('library')} device set:{part_attrib.get('deviceset')}",
                    'product_id': product_id and product_id.id or False,
                    'short_description': short_description,
                    'import_id': self.id
                })

    def _external_import(self):
        for record in self.data_file_external:
            _logger.info(f"record: {record.mimetype}")
            if record.description == _('Generated on base brd file'):
                continue
            if record.mimetype == 'text/plain':
                self._txt_import(record.datas)
            elif record.mimetype in ['text/csv',
                            'application/vnd.ms-excel',
                            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            'application/vnd.oasis.opendocument.spreadsheet'
                            ]:
                self._base_internal_import(record.mimetype, record.datas)

    def _txt_import(self, datas):
        data = {}
        datas = base64.b64decode(datas)
        lines = datas.splitlines()
        # _logger.info(f"{lines}")
        index = ""
        for line in lines:
            line_split = line.split(b';')
            line_split = list(map(lambda x: x.strip(), line_split))
            if len(line_split) >= 1 and line_split[0] != b'':
                _logger.info(f"line_split: {line_split}")
                if line_split[0].startswith(b'#') and line_split[0].split(b' ')[0] not in [b'#P', b'#R', b'#C']:
                    continue
                if line_split[0].startswith(b'#'):
                    index = line_split[0].decode()
                if not data.get(index):
                    data[index] = []
                data[index] += list(map(lambda x: x.decode(), line_split[1:]))

        for key, line in data.items():
            # _logger.info(f"data {key}-{line}")
            if key.startswith('#C'):
                line_to_save = self.line_details.filtered(lambda r: r.designator == line[0])
                _logger.info(f"line: {key}-{line_to_save}-{line}")
                if line_to_save:
                    line_to_save.write({
                        'theta_txt': line[1],
                        'x_coordinate_fiducial_1_txt': line[2],
                        'y_coordinate_fiducial_1_txt': line[3],
                    })

    def _pnp_update(self):
        file_name = self.filename.split('.')[0]
        self.data_file_external.filtered(lambda r: r.name.startswith(file_name)).unlink()

        designation = self.project_bom_id.product_tmpl_id.display_name
        barcode = self.project_bom_id.product_tmpl_id.barcode or '---'
        scale = 1.000
        file_code = '---'
        customer_code = self.env.user.company_id.partner_id.ref or '---'
        date = fields.Date.today().strftime('%d/%m/%y')
        comments = self.comments or 'No cooments'
        user = self.env.user.name
        date_create = self.project_bom_id.create_date
        date_write = self.project_bom_id.write_date
        width = 177.0
        thickness = 1.6
        library = 'ITEM'
        length = 177.0

        reserved = '0'
        board_alignment = '2'
        rejection = '2'
        component_electrical_test = '0'
        fiducial_mark_colour = '2'
        rejection_mark_colour = '2'

        pnp_file_f = ["#D BASE"]
        pnp_file_b = ["#D BASE"]
        file_name_f = file_name + "_F"
        file_name_b = file_name + "_B"

        pnp_items_f = []
        pnp_items_b = []
        pnp_file_f.append(f"#P {file_name_f:<20};{designation:<40};{barcode:<20};{scale:.3f};{file_code:<20};{customer_code:<20};"
                          f"{date};{comments:<72};{user.split(' ')[0]:<12};{date_create.strftime('%d/%m/%y')};{date_create.strftime('%H:%M')};"
                          f"{user.split(' ')[-1]:<12};{date_write.strftime('%d/%m/%y')};{date_write.strftime('%H:%M')};"
                          f"{width:.4f};{thickness:.3f};{library:<8};{length:.4f};1.000")
        pnp_file_f.append(f"#M {file_name_f:<8};0.000;0.000;0.000")

        pnp_file_b.append(f"#P {file_name_b:<20};{designation:<40};{barcode:<20};{scale:.3f};{file_code:<20};{customer_code:<20};"
                          f"{date};{comments:<72};{user.split(' ')[0]:<12};{date_create.strftime('%d/%m/%y')};{date_create.strftime('%H:%M')};"
                          f"{user.split(' ')[-1]:<12};{date_write.strftime('%d/%m/%y')};{date_write.strftime('%H:%M')};"
                          f"{width:.4f};{thickness:.3f};{library:<8};{length:.4f};1.000")
        pnp_file_b.append(f"#M {file_name_b:<8};0.000;0.000;0.000")

        for line in self.line_details:
            default_code = line.product_id.default_code or line.product_id.product_tmpl_id.default_code
            # _logger.info(
            #     f"{line.short_description_semi_product} #C {default_code};{line.designator:<8};{line.theta:.3f};{line.x_coordinate_fiducial_1_txt:.3f};{line.y_coordinate_fiducial_1_txt:.3f}")
            if line.short_description_semi_product == 'F' and default_code:
                pnp_items_f.append(f"#I {default_code:<16};{line.product_id.name and line.product_id.name.strip() or ''};")
                pnp_file_f.append(f"#C {default_code};{line.designator:<8};{line.theta:.3f};{line.x_coordinate_fiducial_1_txt:.3f};{line.y_coordinate_fiducial_1_txt:.3f}")
            elif line.short_description_semi_product == 'B' and default_code:
                pnp_items_b.append(f"#I {default_code:<16};{line.product_id.name and line.product_id.name.strip() or ''};")
                pnp_file_b.append(f"#C {default_code};{line.designator:<8};{line.theta:.3f};{line.x_coordinate_fiducial_1_txt:.3f};{line.y_coordinate_fiducial_1_txt:.3f}")
        pnp_file_f.append(f"#K {reserved:<9};{board_alignment:<9};{rejection:<9};{component_electrical_test:<9};"
                           f"{fiducial_mark_colour:<9};{rejection_mark_colour:<9}")
        pnp_file_f += ["#F", ""]
        pnp_items_f += ["#F", ""]
        pnp_file_f += pnp_items_f

        pnp_file_b.append(f"#K {reserved:<9};{board_alignment:<9};{rejection:<9};{component_electrical_test:<9};"
                           f"{fiducial_mark_colour:<9};{rejection_mark_colour:<9}")
        pnp_file_b += ["#F", ""]
        pnp_items_b += ["#F", ""]
        pnp_file_b += pnp_items_b
        # _logger.info(f"{pnp_file_f}\n{pnp_file_b}")
        pnp_file_f = '\n'.join(map(str, pnp_file_f)).encode(encoding='utf-8')
        pnp_file_b = '\n'.join(map(str, pnp_file_b)).encode(encoding='utf-8')
        self.data_file_external = [Command.create({
            'datas': base64.b64encode(pnp_file_f),
            'name': file_name_f + '.txt',
            'description': _('Generated on base brd file'),
        }), Command.create({
            'datas': base64.b64encode(pnp_file_b),
            'name': file_name_b + '.txt',
            'description': _('Generated on base brd file'),
        })]

    def _get_mimetype(self):
        file_extension = self.filename.split('.')[-1]
        if MIMETYPES.get(file_extension):
            return MIMETYPES[file_extension]
        return False

    def action_upload(self):
        self.ensure_one()

        if self.data_file:
            mimetype = self._get_mimetype()
            if not mimetype:
                raise UserError('Unsupported file format. Please upload a CSV, XLS, or XLSX file.')

            if self.line_details:
                self.line_details.unlink()

            if mimetype in ['text/csv',
                            'application/vnd.ms-excel',
                            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            'application/vnd.oasis.opendocument.spreadsheet'
                            ]:
                self.filename_mimetype = mimetype
                self._base_internal_import(mimetype, self.data_file)
            elif mimetype == 'application/eagle+xml':
                self.filename_mimetype = mimetype
                _logger.info(f"Starting parce brd file {self.filename}")
                self._brd_import()

                _logger.info(f"Starting parce external files {self.data_file_external}")
                self._external_import()

            if self.filename_sch and self.filename_sch.split('.')[-1] == 'sch':
                _logger.info(f"Starting parce sch file")
                self._sch_import()


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
        for record in self:
            for line in record.line_details:
                record.data_file_external = False
                self.env['project.bom.line.details'].create({
                    'project_bom_id': record.project_bom_id.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.qty,
                    'designator': line.designator,
                    'hw_option': line.hw_option.id,
                    'bom_product_template_attribute_value_ids': [Command.set(line.possible_bom_product_template_attribute_value_ids.ids)],
                    'semi_product_tmpl_id': record.semi_product_tmpl_id.id,
                    'semi_product_id': record.semi_product_id.id,
                })

    def action_brd(self):
        self.ensure_one()
        self._brd_update()
        return {
            'name': _('Import BOM Line Details'),
            'view_mode': 'form',
            'res_model': 'project.bom.line.details.import.wizard',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }

    def action_pnp(self):
        self.ensure_one()
        self._pnp_update()
        return {
            'name': _('Import BOM Line Details'),
            'view_mode': 'form',
            'res_model': 'project.bom.line.details.import.wizard',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }

    def action_html(self):
        self.ensure_one()

        config_ibom = Config(version, config.rcfile)
        config_ibom.show_fields = ['Value', 'Footprint', 'MANUFACTURER_PART_NUMBER', 'OPT', 'MecID', 'ArtID', 'theta', 'xFid1', 'yFid1']
        # self._brd_update()

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
        self.data_file_external = [Command.create({
            'datas': base64.b64encode(html.encode('utf-8')),
            'name': f"ibom_{self.filename.split('.')[0]}.html",
            'description': _('Generated on base brd file'),
        })]
        # self.data_file_html = base64.b64encode(html.encode('utf-8'))
        # self.filename_html = 'ibom.html'
        return {
            'name': _('Import BOM Line Details'),
            'view_mode': 'form',
            'res_model': 'project.bom.line.details.import.wizard',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }

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
            if line.short_description_semi_product:
                found_products = self.env['product.product'].search([
                    ('id', '=', self.semi_product_id.id),
                    '|',
                    ('short_description', 'like', line.short_description_semi_product.strip()),
                    ('product_tmpl_id.short_description', 'like', line.short_description_semi_product.strip())
                ])
                if found_products:
                    line.semi_product_id = found_products[0].id
                    line.semi_product_tmpl_id = found_products[0].product_tmpl_id.id
                    if len(found_products) > 1:
                        error_message.append(
                            _(f"{'To many semi products found with some technical description or default code'}"))

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

    @api.onchange('filename')
    def onchange_filename(self):
        for record in self:
            if record.filename:
                record.filename_mimetype = record._get_mimetype()

    @api.onchange('panel_rotation')
    def onchange_panel_rotation(self):
        for record in self:
            for line in record.line_details:
                theta = line.theta + float(record.panel_rotation)
                _logger.info(f"theta: {theta}")
                if theta >= 360:
                    line.theta_txt = theta - 360.0
                else:
                    line.theta_txt = theta
