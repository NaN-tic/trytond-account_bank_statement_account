#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Not, Equal
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = ['StatementLine', 'StatementMoveLine']

POSTED_STATES = {
    'readonly': Not(Equal(Eval('state'), 'confirmed'))
    }
_ZERO = Decimal("0.0")


class StatementLine:
    __name__ = 'account.bank.statement.line'

    lines = fields.One2Many('account.bank.statement.move.line',
        'line', 'Transactions', states=POSTED_STATES,
        context={
            'amount': Eval('amount'),
            'date': Eval('date'),
            'moves_amount': Eval('moves_amount'),
            })

    @classmethod
    def __setup__(cls):
        super(StatementLine, cls).__setup__()
        if 'lines' not in cls.moves_amount.on_change_with:
            cls.moves_amount.on_change_with.append('lines')

    @classmethod
    def post(cls, statement_lines):
        for st_line in statement_lines:
            for line in st_line.lines:
                line.create_move()
        super(StatementLine, cls).post(statement_lines)

    def on_change_with_moves_amount(self):
        res = super(StatementLine, self).on_change_with_moves_amount()
        if getattr(self, 'state', None) == 'posted':
            return res
        return res + sum(l.amount or Decimal('0.0') for l in self.lines)

    @classmethod
    def cancel(cls, statement_lines):
        super(StatementLine, cls).cancel(statement_lines)
        with Transaction().set_context({
                    'from_account_bank_statement_line': True,
                    }):
            for st_line in statement_lines:
                st_line.reset_account_move()

    def reset_account_move(self):
        pool = Pool()
        Move = pool.get('account.move')
        delete_moves = [x.move for x in self.lines if x.move]
        Move.draft(delete_moves)
        Move.delete(delete_moves)


class StatementMoveLine(ModelSQL, ModelView):
    'Statement Move Line'
    __name__ = 'account.bank.statement.move.line'

    line = fields.Many2One('account.bank.statement.line', 'Line',
        required=True, ondelete='CASCADE')
    date = fields.Date('Date', required=True)
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('_parent_statement', {}).get('currency_digits', 2)),
        on_change=['amount', 'party', 'account', 'invoice',
            '_parent_line.journal'])
    party = fields.Many2One('party.party', 'Party',
            on_change=['account', 'amount', 'party', 'invoice'])
    account = fields.Many2One('account.account', 'Account', required=True,
        on_change=['account', 'invoice'], domain=[
            ('company', '=', Eval('_parent_line', {}).get('company', 0)),
            ('kind', '!=', 'view'),
            ])
    description = fields.Char('Description')
    move = fields.Many2One('account.move', 'Account Move', readonly=True)

    @classmethod
    def __setup__(cls):
        super(StatementMoveLine, cls).__setup__()
        cls._sql_constraints += [(
                'check_bank_move_amount', 'CHECK(amount != 0)',
                'Amount should be a positive or negative value.'),
        ]
        cls._error_messages.update({
                'debit_credit_account_not_bank_reconcile': (
                    'The credit or debit account of Journal "%s" is not '
                    'checked as "Bank Conciliation".'),
                'debit_credit_account_statement_journal': ('Please provide '
                    'debit and credit account on statement journal "%s".'),
                'same_debit_credit_account': ('Account "%(account)s" in '
                    'statement line "%(line)s" is the same as the one '
                    'configured as credit or debit on journal "%(journal)s".'),
                })

    @staticmethod
    def default_amount():
        context = Transaction().context
        if 'amount' in context and 'moves_amount' in context:
            return context['amount'] - context['moves_amount']
        return Decimal(0)

    @staticmethod
    def default_date():
        if Transaction().context.get('date'):
            return Transaction().context.get('date').date()
        return None

    def on_change_party(self):
        res = {}
        if self.party and self.amount:
            if self.amount > Decimal("0.0"):
                account = self.account or self.party.account_receivable
            else:
                account = self.account or self.party.account_payable
            res['account'] = account.id
            res['account.rec_name'] = account.rec_name
        return res

    def on_change_amount(self):
        res = {}
        if self.party and not self.account and self.amount:
            if self.amount > Decimal("0.0"):
                account = self.party.account_receivable
            else:
                account = self.party.account_payable
            res['account'] = account.id
            res['account.rec_name'] = account.rec_name
        return res

    def on_change_account(self):
        res = {}
        if self.invoice:
            if self.account:
                if self.invoice.account != self.account:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    def get_rec_name(self, name):
        return self.line.rec_name

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('move', None)
        default.setdefault('invoice', None)
        return super(StatementMoveLine, cls).copy(lines, default=default)

    def create_move(self):
        '''
        Create move for the statement line and return move if created.
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        if self.move:
            return

        period_id = Period.find(self.line.company.id, date=self.date)

        move_lines = self._get_move_lines()
        move = Move(
            period=period_id,
            journal=self.line.journal.journal,
            date=self.date,
            lines=move_lines,
            )
        move.save()
        Move.post([move])

        journal = self.line.journal.journal
        accounts = [journal.credit_account, journal.debit_account]

        st_move_line, = [x for x in move.lines if x.account in accounts]
        bank_line, = st_move_line.bank_lines
        bank_line.bank_statement_line = self.line
        bank_line.save()

        self.move = move
        self.save()
        return move

    @classmethod
    def post_move(cls, lines):
        Move = Pool().get('account.move')
        Move.post([l.move for l in lines if l.move])

    @classmethod
    def delete_move(cls, lines):
        Move = Pool().get('account.move')
        Move.delete([l.move for l in lines if l.move])

    def _get_move_lines(self):
        '''
        Return the move lines for the statement line
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Currency = Pool().get('currency.currency')
        amount = Currency.compute(self.line.journal.currency, self.amount,
            self.line.company.currency)
        if self.line.journal.currency != self.line.company.currency:
            second_currency = self.line.journal.currency.id
            amount_second_currency = abs(self.amount)
        else:
            amount_second_currency = None
            second_currency = None

        move_lines = []
        move_lines.append(MoveLine(
                description=self.description,
                debit=amount < _ZERO and -amount or _ZERO,
                credit=amount >= _ZERO and amount or _ZERO,
                account=self.account,
                party=self.party,
                second_currency=second_currency,
                amount_second_currency=amount_second_currency,
                ))

        journal = self.line.journal.journal
        if self.amount >= _ZERO:
            account = journal.credit_account
        else:
            account = journal.debit_account

        if not account:
            self.raise_user_error('debit_credit_account_statement_journal',
                journal.rec_name)
        if not account.bank_reconcile:
            self.raise_user_error('debit_credit_account_not_bank_reconcile',
                journal.rec_name)
        if self.account == account:
            self.raise_user_error('same_debit_credit_account', {
                    'account': self.account.rec_name,
                    'line': self.account,
                    'journal': self.journal,
                    })

        bank_move = MoveLine(
            description=self.description,
            debit=amount >= _ZERO and amount or _ZERO,
            credit=amount < _ZERO and -amount or _ZERO,
            account=account,
            party=self.party,
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            )
        move_lines.append(bank_move)
        return move_lines
