===============================
Account Bank Statement Scenario
===============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> now = datetime.datetime.now()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_bank_statement::

    >>> Module = Model.get('ir.module.module')
    >>> account_bank_module, = Module.find(
    ...     [('name', '=', 'account_bank_statement_account')])
    >>> Module.install([account_bank_module.id], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

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

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> account_tax, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Main Tax'),
    ...         ])
    >>> cash, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Main Cash'),
    ...         ])
    >>> cash.bank_reconcile = True
    >>> cash.reconcile = True
    >>> cash.save()
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create journals::

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

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create 2 customer invoices::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> customer_invoice1 = Invoice(type='out_invoice')
    >>> customer_invoice1.party = customer
    >>> customer_invoice1.payment_term = payment_term
    >>> invoice_line = InvoiceLine()
    >>> customer_invoice1.lines.append(invoice_line)
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('100')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_invoice1.save()
    >>> Invoice.post([customer_invoice1.id], config.context)
    >>> customer_invoice1.state
    u'posted'

Create 1 customer credit note::

    >>> customer_credit_note = Invoice(type='out_credit_note')
    >>> customer_credit_note.party = customer
    >>> customer_credit_note.payment_term = payment_term
    >>> invoice_line = InvoiceLine()
    >>> customer_credit_note.lines.append(invoice_line)
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('50')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_credit_note.save()
    >>> Invoice.post([customer_credit_note.id], config.context)
    >>> customer_credit_note.state
    u'posted'


Create 1 supplier invoices::

    >>> supplier_invoice = Invoice(type='in_invoice')
    >>> supplier_invoice.party = supplier
    >>> supplier_invoice.payment_term = payment_term
    >>> invoice_line = InvoiceLine()
    >>> supplier_invoice.lines.append(invoice_line)
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('50')
    >>> invoice_line.account = expense
    >>> invoice_line.description = 'Test'
    >>> supplier_invoice.invoice_date = today
    >>> supplier_invoice.save()
    >>> Invoice.post([supplier_invoice.id], config.context)
    >>> supplier_invoice.state
    u'posted'

Create bank statement::

    >>> statement = BankStatement(journal=statement_journal, date=now)
    >>> statement_line = statement.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Invoice'
    >>> statement_line.amount = Decimal('80.00')
    >>> statement_line = statement.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Credit Note'
    >>> statement_line.amount = Decimal('-50.00')
    >>> statement_line = statement.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Supplier'
    >>> statement_line.amount = Decimal('-50.00')
    >>> statement.click('confirm')
    >>> statement.state
    u'confirmed'
    >>> customer_line, credit_note_line, supplier_line = statement.lines

Received 80 from customer::

    >>> move_line = customer_line.lines.new()
    >>> move_line.amount
    Decimal('80.00')
    >>> move_line.invoice = customer_invoice1
    >>> move_line.party == customer
    True
    >>> move_line.account == receivable
    True
    >>> customer_line.save()

Paid 50 to customer::

    >>> move_line = credit_note_line.lines.new()
    >>> move_line.amount
    Decimal('-50.00')
    >>> move_line.invoice = supplier_invoice
    >>> move_line.party == supplier
    True
    >>> move_line.account == payable
    True
    >>> credit_note_line.save()

Paid 50 to supplier::

    >>> move_line = supplier_line.lines.new()
    >>> move_line.amount
    Decimal('-50.00')
    >>> move_line.invoice = customer_credit_note
    >>> move_line.party == customer
    True
    >>> move_line.account == receivable
    True
    >>> supplier_line.save()

Confirm the statement and post its lines::

    >>> for line in statement.lines:
    ...     line.click('post')

Test invoice state::

    >>> customer_invoice1.reload()
    >>> customer_invoice1.state
    u'posted'
    >>> customer_invoice1.amount_to_pay
    Decimal('20.00')
    >>> customer_credit_note.reload()
    >>> customer_credit_note.state
    u'paid'
    >>> supplier_invoice.reload()
    >>> supplier_invoice.state
    u'paid'
