#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from trytond.pool import Pool
from .invoice import *
from .statement import *


def register():
    Pool.register(
        Invoice,
        StatementLine,
        StatementMoveLine,
        module='account_bank_statement_account', type_='model')
