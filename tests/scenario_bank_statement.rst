===============================
Account Bank Statement Scenario
===============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from.trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()
    >>> now = datetime.datetime.now()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_bank_statement::

    >>> Module = Model.get('ir.module')
    >>> account_bank_module, = Module.find(
    ...     [('name', '=', 'account_bank_statement_account')])
    >>> Module.install([account_bank_module.id], config.context)
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']
    >>> cash.bank_reconcile = True
    >>> cash.reconcile = True
    >>> cash.save()

    >>> Journal = Model.get('account.journal')
    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> cash_journal.credit_account = cash
    >>> cash_journal.debit_account = cash
    >>> cash_journal.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create journals::

    >>> Sequence = Model.get('ir.sequence')
    >>> sequence = Sequence(name='Bank', code='account.journal',
    ...     company=company)
    >>> sequence.save()
    >>> AccountJournal = Model.get('account.journal')
    >>> account_journal = AccountJournal(name='Statement',
    ...     type='cash',
    ...     credit_account=cash,
    ...     debit_account=cash,
    ...     sequence=sequence)
    >>> account_journal.save()
    >>> StatementJournal = Model.get('account.bank.statement.journal')
    >>> statement_journal = StatementJournal(name='Test',
    ...     journal=account_journal)
    >>> statement_journal.save()

Create move::

    >>> period = fiscalyear.periods[0]
    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = account_journal
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal('80.0')
    >>> line2 = move.lines.new()
    >>> line2.account = receivable
    >>> line2.credit = Decimal('80.0')
    >>> line2.party = party
    >>> move.save()
    >>> move.reload()
    >>> Move.post([move.id], config.context)
    >>> move.reload()
    >>> move.state
    u'posted'

Create bank statement::

    >>> BankStatement = Model.get('account.bank.statement')
    >>> statement = BankStatement(journal=statement_journal, date=now)

Create bank statement lines::

    >>> StatementLine = Model.get('account.bank.statement.line')
    >>> statement_line = StatementLine()
    >>> statement.lines.append(statement_line)
    >>> statement_line.date = now
    >>> statement_line.description = 'Statement Line'
    >>> statement_line.amount = Decimal('80.0')
    >>> statement_line.account = revenue
    >>> statement.save()
    >>> statement.reload()
    >>> BankStatement.confirm([statement.id], config.context)
    >>> statement.reload()
    >>> statement.state
    u'confirmed'
    >>> statement_line, = statement.lines
    >>> StatementMoveLine = Model.get('account.bank.statement.move.line')
    >>> st_move_line = StatementMoveLine()
    >>> st_move_line.amount = Decimal('80.0')
    >>> st_move_line.line = statement_line
    >>> st_move_line.account = revenue
    >>> st_move_line.date = today
    >>> st_move_line.description = 'Description'
    >>> st_move_line.save()
    >>> st_move_line.reload()
    >>> StatementLine.post([statement_line.id], config.context)
    >>> statement_line.company_amount == Decimal('80.0')
    True
    >>> st_move_line.move.description == 'Description'
    True
    >>> set([x.description for x in st_move_line.move.lines]) == set(
    ...         ['Description'])
    True
