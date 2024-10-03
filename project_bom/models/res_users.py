# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class Users(models.Model):
    _name = "res.users"
    _inherit = ['res.users', 'nexar.client.mixin']

    def __init__(self, env, ids=(), prefetch_ids=()):
        super().__init__(env, ids=ids, prefetch_ids=prefetch_ids)
        env.cr.execute("SELECT column_name FROM information_schema.columns "
                       "WHERE table_name = 'res_users' AND column_name = 'nexar_token'")
        if not env.cr.fetchone():
            env.cr.execute('ALTER TABLE res_users '
                           'ADD COLUMN nexar_token varchar;')

        env.cr.execute("SELECT column_name FROM information_schema.columns "
                       "WHERE table_name = 'res_users' AND column_name = 'nexar_client_id'")
        if not env.cr.fetchone():
            env.cr.execute('ALTER TABLE res_users '
                           'ADD COLUMN nexar_client_id varchar;')

        env.cr.execute("SELECT column_name FROM information_schema.columns "
                       "WHERE table_name = 'res_users' AND column_name = 'nexar_client_secret'")
        if not env.cr.fetchone():
            env.cr.execute('ALTER TABLE res_users '
                           'ADD COLUMN nexar_client_secret varchar;')

        env.cr.execute("SELECT column_name FROM information_schema.columns "
                       "WHERE table_name = 'res_users' AND column_name = 'nexar_exp'")
        if not env.cr.fetchone():
            env.cr.execute('ALTER TABLE res_users '
                           'ADD COLUMN nexar_exp timestamp;')
