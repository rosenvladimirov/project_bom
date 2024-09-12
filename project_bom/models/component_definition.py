# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _


class ComponentsDefinition(models.Model):
    _name = 'component.definition.properties'
    _description = 'Component Definition Properties'
    _rec_name = 'code'

    sequence = fields.Integer('Sequence')
    code = fields.Char('Code')
    name = fields.Char('Name')
    component_properties_definition = fields.PropertiesDefinition('Component Capacitance definitions')


class ComponentDefinitionPackages(models.Model):
    _name = "component.definition.packages"
    _description = "Component Definition Case/Packages"

    code = fields.Char('Code')
    name = fields.Char('Case/Packages')
    length = fields.Float('Length')
    width = fields.Float('Width')
    height = fields.Float('Height')
