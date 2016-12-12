# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def check_modify(cls, *args, **kwargs):
        if Transaction().context.get('from_account_bank_statement_line'):
            return
        return super(Move, cls).check_modify(*args, **kwargs)


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    @classmethod
    def check_modify(cls, *args, **kwargs):
        if Transaction().context.get('from_account_bank_statement_line'):
            return
        return super(MoveLine, cls).check_modify(*args, **kwargs)
