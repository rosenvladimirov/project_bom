{
    'name': 'Product Variant Config',
    'description': 'Product Variant Configuration',
    'version': '17.0.1.0.0',
    'category': 'Product',
    'depends': [
        'sale',
        'product',
        'purchase',
        'sale_product_configurator',
        'web_widget_x2many_2d_matrix',
        'web'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'wizards/product_template_attribute_config_wizard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pv_config/static/src/**/*',
        ]
    },
}
