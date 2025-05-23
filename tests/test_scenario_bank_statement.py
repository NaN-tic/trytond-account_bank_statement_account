from trytond.modules.account_invoice.tests.tools import set_fiscalyear_invoice_sequences
from trytond.modules.account.tests.tools import create_fiscalyear, create_chart, get_accounts
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.tools import activate_modules
from proteus import Model
from decimal import Decimal
import datetime
import unittest
from trytond.tests.test_tryton import drop_db

class Test(unittest.TestCase):
    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        today = datetime.date.today()
        now = datetime.datetime.now()

        # Install account_bank_statment_account Module
        activate_modules('account_bank_statement_account')

        # Create company
        currency = get_currency('EUR')
        _ = create_company(currency=currency)
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        receivable = accounts['receivable']
        revenue = accounts['revenue']
        cash = accounts['cash']
        cash.bank_reconcile = True
        cash.reconcile = True
        cash.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        # Create journals
        AccountJournal = Model.get('account.journal')
        account_journal = AccountJournal(name='Statement', type='cash')
        account_journal.save()
        StatementJournal = Model.get('account.bank.statement.journal')
        statement_journal = StatementJournal(name='Test',
            journal=account_journal, account=cash)
        statement_journal.save()

        # Create move
        period = fiscalyear.periods[0]
        Move = Model.get('account.move')
        move = Move()
        move.period = period
        move.journal = account_journal
        move.date = period.start_date
        line = move.lines.new()
        line.account = cash
        line.debit = Decimal('80.0')
        line2 = move.lines.new()
        line2.account = receivable
        line2.credit = Decimal('80.0')
        line2.party = party
        move.click('post')
        self.assertEqual(move.state, 'posted')

        # Create bank statement
        BankStatement = Model.get('account.bank.statement')
        statement = BankStatement(journal=statement_journal, date=now)

        # Create bank statement lines
        StatementLine = Model.get('account.bank.statement.line')
        statement_line = StatementLine()
        statement.lines.append(statement_line)
        statement_line.date = now
        statement_line.description = 'Statement Line'
        statement_line.amount = Decimal('80.0')
        statement_line.account = revenue
        statement.click('confirm')
        self.assertEqual(statement.state, 'confirmed')
        statement_line, = statement.lines
        StatementMoveLine = Model.get('account.bank.statement.move.line')
        st_move_line = StatementMoveLine()
        st_move_line.amount = Decimal('80.0')
        st_move_line.line = statement_line
        st_move_line.account = revenue
        st_move_line.date = today
        st_move_line.description = 'Description'
        st_move_line.save()
        statement_line.click('post')
        self.assertEqual(statement_line.company_amount, Decimal('80.00'))
        self.assertEqual(st_move_line.move.description, 'Description')
        self.assertEqual(set([x.move_description_used for x in st_move_line.move.lines]), set(['Description']))
        self.assertEqual(set([x.description_used for x in st_move_line.move.lines]), set(['Statement Line']))
