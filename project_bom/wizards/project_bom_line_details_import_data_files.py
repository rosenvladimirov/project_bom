# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _, api
from .project_bom_line_details_import_wizard import MIMETYPES

class ProjectBomLineDetailsImportDataFile(models.TransientModel):
    _name = 'project.bom.line.details.import.data.files'
    _description = 'Project BOM line details (CAD data file)'

    name = fields.Char(string='Display Name', compute="_compute_display_name", store=True)
    datas = fields.Binary(string='File PnP')
    filename = fields.Char(string='Filename PnP')
    mimetype = fields.Char(string='Mimetype PnP')

    def _compute_display_name(self):
        for record in self:
            record.name = self.filename

    @api.onchange('filename')
    def onchange_filename(self):
        for record in self:
            if record.filename:
                record.mimetype = MIMETYPES.get(record.filename.split('.')[-1])
