# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields, Check
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, Equal, If, Bool
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from sql import Null
from trytond.modules.currency.fields import Monetary


POSTED_STATES = {
    'readonly': Not(Equal(Eval('state'), 'confirmed'))
    }
_ZERO = Decimal("0.0")


class StatementLine(metaclass=PoolMeta):
    __name__ = 'account.bank.statement.line'

    lines = fields.One2Many('account.bank.statement.move.line',
        'line', 'Transactions', states=POSTED_STATES)

    @classmethod
    @ModelView.button
    def post(cls, statement_lines):
        for st_line in statement_lines:
            for line in st_line.lines:
                line.create_move()
        super(StatementLine, cls).post(statement_lines)

    @fields.depends('state', 'company_currency', 'lines')
    def on_change_with_moves_amount(self, name=None):
        amount = super(StatementLine, self).on_change_with_moves_amount(name)
        amount += sum(x.amount or Decimal('0.0') for x in self.lines)
        if self.company_currency:
            amount = self.company_currency.round(amount)
        return amount

    @classmethod
    @ModelView.button
    def cancel(cls, statement_lines):
        with Transaction().set_context({
                    'from_account_bank_statement_line': True,
                    }):
            super(StatementLine, cls).cancel(statement_lines)
            for st_line in statement_lines:
                st_line.reset_account_move()

    def reset_account_move(self):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Reconciliation = pool.get('account.move.reconciliation')

        cancel_moves = [x.move for x in self.lines if x.move]
        reconciliations = [x.reconciliation for m in cancel_moves
            for x in m.lines if x.reconciliation]
        if reconciliations:
            Reconciliation.delete(reconciliations)
        if cancel_moves:
            for move in cancel_moves:
                cancel_move = move.cancel()

            lines = [l for l in move + cancel_move if l.account.reconcile]
            MoveLine.reconcilie(lines)
            cancel_move.origin = self
            cancel_move.save()


class StatementMoveLine(ModelSQL, ModelView):
    'Statement Move Line'
    __name__ = 'account.bank.statement.move.line'

    line = fields.Many2One('account.bank.statement.line', 'Line',
        required=True, ondelete='CASCADE')
    date = fields.Date('Date', required=True)
    currency = fields.Function(fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    amount = Monetary('Amount', required=True,
        currency='currency', digits='currency')
    party = fields.Many2One('party.party', 'Party',
        states={
            'required': Eval('party_required', False),
            'invisible': ~Eval('party_required', False),
            },
        depends=['party_required'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('_parent_line', {}).get('company', 0)),
            ('type', '!=', Null),
            ], depends=['line'])
    description = fields.Char('Description')
    move = fields.Many2One('account.move', 'Account Move', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
        domain=[
            ('company', '=', Eval('_parent_line', {}).get('company', 0)),
            If(Bool(Eval('party')), [('party', '=', Eval('party'))], []),
            If(Bool(Eval('account')), [('account', '=', Eval('account'))], []),
            If(Eval('_parent_line', {}).get('state') != 'posted',
                ('state', '=', 'posted'),
                ('state', '!=', '')),
            ],
        depends=['line', 'party', 'account'])

    @classmethod
    def __setup__(cls):
        super(StatementMoveLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [(
                'check_bank_move_amount', Check(t, t.amount != 0),
                'Amount should be a positive or negative value.'),
        ]

    @fields.depends('line', '_parent_line.statement')
    def on_change_with_currency(self, name=None):
        if (self.line and self.line.statement.company and
                self.line.statement.company.currency):
            return self.line.statement.company.currency.id

    @fields.depends('_parent_line.date', 'line')
    def on_change_with_date(self):
        if self.line and self.line.date:
            return self.line.date.date()

    @fields.depends('_parent_line.company_amount', '_parent_line.moves_amount',
        'line')
    def on_change_with_amount(self):
        if self.line:
            return self.line.company_amount - (self.line.moves_amount or _ZERO)

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required
        return False

    @fields.depends('account', 'amount', 'party', 'invoice')
    def on_change_party(self):
        if self.party and self.amount:
            if self.amount > Decimal("0.0"):
                account = self.account or self.party.account_receivable
            else:
                account = self.account or self.party.account_payable
            self.account = account
        if self.invoice:
            if self.party:
                if self.invoice.party != self.party:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('amount', 'party', 'account', 'invoice',
        '_parent_line.journal', 'line')
    def on_change_amount(self):
        Currency = Pool().get('currency.currency')
        if self.party and not self.account and self.amount:
            if self.amount > Decimal("0.0"):
                account = self.party.account_receivable
            else:
                account = self.party.account_payable
            self.account = account
        if self.invoice:
            if self.amount and self.line and self.line.journal:
                invoice = self.invoice
                journal = self.line.journal
                with Transaction().set_context(date=invoice.currency_date):
                    amount_to_pay = Currency.compute(invoice.currency,
                        invoice.amount_to_pay, journal.currency)
                if abs(self.amount) > amount_to_pay:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('account', 'invoice')
    def on_change_account(self):
        if self.invoice:
            if self.account:
                if self.invoice.account != self.account:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('party', 'account', 'invoice')
    def on_change_invoice(self):
        if self.invoice:
            if not self.party:
                self.party = self.invoice.party
            if not self.account:
                self.account = self.invoice.account

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
        Currency = pool.get('currency.currency')
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        if self.move:
            return

        move = self._get_move()
        move.save()
        Move.post([move])

        self.move = move
        self.save()
        if self.invoice:
            self._check_invoice_amount_to_pay()

            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.line.journal.currency,
                    self.amount, self.line.company_currency)

            reconcile_lines = self.invoice.get_reconcile_lines_for_amount(
                amount, self.line.company_currency)
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

    def _check_invoice_amount_to_pay(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Lang = pool.get('ir.lang')

        if not self.invoice:
            return
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
            raise UserError(gettext(
                'account_bank_statement_account.'
                'amount_greater_invoice_amount_to_pay', amount=amount))

    def _get_move(self):
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        period_id = Period.find(self.line.company.id, date=self.date)

        move_lines = self._get_move_lines()
        return Move(
            period=period_id,
            journal=self.line.journal.journal,
            date=self.date,
            lines=move_lines,
            description=self.description,
            origin=self.line.statement,
            )

    def _get_move_lines(self):
        '''
        Return the move lines for the statement line
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Currency = Pool().get('currency.currency')
        amount = self.amount
        if ((self.line.journal.currency != self.line.company.currency) or
                (self.account and self.account.second_currency)):
            if (self.account and self.account.second_currency and
                    self.account.second_currency != self.line.journal.currency):
                raise UserError(
                    gettext('account_bank_statement_account.'
                        'account_statement_line_currency',
                        journal=self.line.journal.rec_name,
                        account=self.account.rec_name))
            second_currency = self.line.journal.currency.id
            with Transaction().set_context(date=self.line.date.date()):
                amount_second_currency = abs(Currency.compute(
                        self.line.company.currency, self.amount,
                        self.line.journal.currency))
                if amount >= _ZERO:
                    amount_second_currency = -amount_second_currency
        else:
            amount_second_currency = None
            second_currency = None

        move_lines = []
        move_lines.append(MoveLine(
                description=self.description,
                debit=amount < _ZERO and -amount or _ZERO,
                credit=amount >= _ZERO and amount or _ZERO,
                account=self.account,
                party=self.party if self.account.party_required else None,
                second_currency=second_currency,
                amount_second_currency=amount_second_currency,
                origin=self.line,
                ))

        journal = self.line.journal
        account = journal.account

        if not account:
            raise UserError(
            gettext('account_bank_statement_account.'
                'account_statement_journal', journal=journal.rec_name))
        if not account.bank_reconcile:
            raise UserError(
            gettext('account_bank_statement_account.'
                'account_not_bank_reconcile', journal=journal.rec_name))
        if self.account == account:
            raise UserError(
                gettext('account_bank_statement_account.same_account',
                    account=self.account.rec_name,
                    line=self.rec_name,
                    journal=self.line.journal.rec_name))

        if amount_second_currency:
            amount_second_currency = -amount_second_currency
        bank_move = MoveLine(
            description=self.description,
            debit=amount >= _ZERO and amount or _ZERO,
            credit=amount < _ZERO and -amount or _ZERO,
            account=account,
            party=(self.party or self.line.company.party
                if account.party_required else None),
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            origin=self.line,
            move_origin=self.line.statement,
            )
        move_lines.append(bank_move)
        return move_lines
