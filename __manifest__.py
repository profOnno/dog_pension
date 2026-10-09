{
    'name': 'Dog Pension',
    'version': '19.0.1.0.0',
    'summary': 'Manage a dog pension: customers, dogs, and stays',
    'description': """
        Dog Pension Management
        ======================
        - Customers can own multiple dogs
        - Each dog can have stays at the pension for a specific period
        - The stay period is requested directly at the Sales Order
    """,
    'category': 'Services',
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': ['base', 'sale_management', 'product'],
    'data': [
        'security/dog_pension_security.xml',
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'wizard/dog_quick_create_views.xml',
        'report/paperformat.xml',
        'report/kennel_card_template.xml',
        'report/kennel_card_template.xml',
        'report/report.xml',                # ← report action defined here
        'views/room_views.xml',
        'views/hallway_views.xml',
        'views/kennel_views.xml',
        'views/dog_views.xml',
        'views/dog_stay_views.xml',         # ← references the action
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/menus.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
