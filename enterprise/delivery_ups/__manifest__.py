# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "UPS Shipping",
    'description': "Send your shippings through UPS and track them online",
    'category': 'Warehouse',
    'version': '1.0',
    'depends': ['delivery', 'mail'],
    'data': [
        'data/delivery_ups_data.xml',
        'views/delivery_ups_view.xml'
    ],
    'license': 'OEEL-1',
    'uninstall_hook': 'uninstall_hook',
}
