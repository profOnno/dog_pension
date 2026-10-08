from . import models
from . import wizard

def post_init_hook(env):
    dogs = env['dog.pension.dog'].search([])
    dogs._compute_qr_code()
    kennels = env['dog.pension.kennel'].search([])
    kennels._compute_qr_code()
