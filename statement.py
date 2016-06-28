#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Not, Equal, If, Bool
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
            'bank_statement_amount': Eval('company_amount', 0),
            'bank_statement_date': Eval('date', None),
            'bank_statement_moves_amount': Eval('moves_amount', 0),
            })

    @classmethod
    def __setup__(cls):
        super(StatementLine, cls).__setup__()
        if 'lines' not in cls.moves_amount.on_change_with:
            cls.moves_amount.on_change_with.add('lines')

    @classmethod
    @ModelView.button
    def post(cls, statement_lines):
        for st_line in statement_lines:
            for line in st_line.lines:
                line.create_move()
        super(StatementLine, cls).post(statement_lines)

    @fields.depends('state', 'lines')
    def on_change_with_moves_amount(self):
        res = super(StatementLine, self).on_change_with_moves_amount()
        if self.state == 'posted':
            return res
        return res + sum(l.amount or Decimal('0.0') for l in self.lines)

    @classmethod
    @ModelView.button
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
        Reconciliation = pool.get('account.move.reconciliation')

        Reconciliation = pool.get('account.move.reconciliation')
        delete_moves = [x.move for x in self.lines if x.move]
        reconciliations = [x.reconciliation for m in delete_moves
            for x in m.lines if x.reconciliation]
        if reconciliations:
            Reconciliation.delete(reconciliations)
        Move.draft(delete_moves)
        Move.delete(delete_moves)


class StatementMoveLine(ModelSQL, ModelView):
    'Statement Move Line'
    __name__ = 'account.bank.statement.move.line'

    line = fields.Many2One('account.bank.statement.line', 'Line',
        required=True, ondelete='CASCADE')
    date = fields.Date('Date', required=True)
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('_parent_statement', {}).get('currency_digits', 2)))
    party = fields.Many2One('party.party', 'Party',
        states={
            'required': Eval('party_required', False),
            },
        depends=['party_required'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('_parent_line', {}).get('company', 0)),
            ('kind', '!=', 'view'),
            ])
    description = fields.Char('Description')
    move = fields.Many2One('account.move', 'Account Move', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
        domain=[
            If(Bool(Eval('party')), [('party', '=', Eval('party'))], []),
            If(Bool(Eval('account')), [('account', '=', Eval('account'))], []),
            If(Eval('_parent_line', {}).get('state') != 'posted',
                ('state', '=', 'posted'),
                ('state', '!=', '')),
            ],
        depends=['party', 'account'])

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
                'amount_greater_invoice_amount_to_pay': ('Amount "%s" is '
                    'greater than the amount to pay of invoice.'),
                })

    @staticmethod
    def default_amount():
        context = Transaction().context
        if ('bank_statement_amount' in context and
                'bank_statement_moves_amount' in context):
            return (Decimal(context['bank_statement_amount'])
                - Decimal(context['bank_statement_moves_amount']))
        return Decimal(0)

    @staticmethod
    def default_date():
        if Transaction().context.get('bank_statement_date'):
            return Transaction().context.get('bank_statement_date').date()
        return None

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required
        return False

    @fields.depends('account', 'amount', 'party', 'invoice')
    def on_change_party(self):
        res = {}
        if self.party and self.amount:
            if self.amount > Decimal("0.0"):
                account = self.account or self.party.account_receivable
            else:
                account = self.account or self.party.account_payable
            res['account'] = account.id
            res['account.rec_name'] = account.rec_name
        if self.invoice:
            if self.party:
                if self.invoice.party != self.party:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    @fields.depends('amount', 'party', 'account', 'invoice',
        '_parent_line.journal')
    def on_change_amount(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        res = {}
        if self.party and not self.account and self.amount:
            if self.amount > Decimal("0.0"):
                account = self.party.account_receivable
            else:
                account = self.party.account_payable
            res['account'] = account.id
            res['account.rec_name'] = account.rec_name
        if self.invoice:
            if self.amount and self.line and self.line.journal:
                invoice = self.invoice
                journal = self.line.journal
                with Transaction().set_context(date=invoice.currency_date):
                    amount_to_pay = Currency.compute(invoice.currency,
                        invoice.amount_to_pay, journal.currency)
                if abs(self.amount) > amount_to_pay:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    @fields.depends('account', 'invoice')
    def on_change_account(self):
        res = {}
        if self.invoice:
            if self.account:
                if self.invoice.account != self.account:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    @fields.depends('party', 'account', 'invoice')
    def on_change_invoice(self):
        changes = {}
        if self.invoice:
            if not self.party:
                changes['party'] = self.invoice.party.id
                changes['party.rec_name'] = self.invoice.party.rec_name
            if not self.account:
                changes['account'] = self.invoice.account.id
                changes['account.rec_name'] = self.invoice.account.rec_name
        return changes

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
        Currency = pool.get('currency.currency')
        Lang = pool.get('ir.lang')
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        if self.move:
            return

        period_id = Period.find(self.line.company.id, date=self.date)

        move_lines = self._get_move_lines()
        move = Move(
            period=period_id,
            journal=self.line.journal.journal,
            date=self.date,
            lines=move_lines,
            description=self.description,
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
        if self.invoice:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount_to_pay = Currency.compute(self.invoice.currency,
                    self.invoice.amount_to_pay,
                    self.line.company_currency)
            if abs(amount_to_pay) < abs(self.amount):
                lang, = Lang.search([
                        ('code', '=', Transaction().language),
                        ])

                amount = Lang.format(lang,
                    '%.' + str(self.line.company_currency.digits) + 'f',
                    self.amount, True)
                self.raise_user_error('amount_greater_invoice_amount_to_pay',
                        error_args=(amount,))

            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.line.journal.currency,
                    self.amount, self.line.company_currency)

            reconcile_lines = self.invoice.get_reconcile_lines_for_amount(
                amount)

            for move_line in move.lines:
                if move_line.account == self.invoice.account:
                    Invoice.write([self.invoice], {
                            'payment_lines': [('add', [move_line.id])],
                            })
                    break
            if reconcile_lines[1] == Decimal('0.0'):
                lines = reconcile_lines[0] + [move_line]
                MoveLine.reconcile(lines)
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
        amount = self.amount
        if self.line.journal.currency != self.line.company.currency:
            second_currency = self.line.journal.currency.id
            with Transaction().set_context(date=self.line.date.date()):
                amount_second_currency = abs(Currency.compute(
                        self.line.company.currency, self.amount,
                        self.line.journal.currency))
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
                    'line': self.rec_name,
                    'journal': self.line.journal.rec_name,
                    })

        bank_move = MoveLine(
            description=self.description,
            debit=amount >= _ZERO and amount or _ZERO,
            credit=amount < _ZERO and -amount or _ZERO,
            account=account,
            party=(self.party or self.line.company.party
                if account.party_required else None),
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            )
        move_lines.append(bank_move)
        return move_lines
