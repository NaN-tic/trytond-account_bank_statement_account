#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from trytond.pool import Pool
from . import invoice
from . import statement


def register():
    Pool.register(
        invoice.Invoice,
        statement.StatementLine,
        statement.StatementMoveLine,
        module='account_bank_statement_account', type_='model')
