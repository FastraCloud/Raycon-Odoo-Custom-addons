# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, SUPERUSER_ID

import models


def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['delivery.carrier'].search([
        ('delivery_type', '=', 'usps')
    ]).write({'delivery_type': 'fixed', 'fixed_price': 0})
