# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

class ProductProduct(models.Model):
    _inherit = "product.product"

    short_description = fields.Char(string='Short Description', maxsize=40)
