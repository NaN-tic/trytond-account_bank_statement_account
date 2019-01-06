from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['Invoice']


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, invoices):
        StatementMoveLine = Pool().get('account.bank.statement.move.line')
        invoice_ids = [x.id for x in invoices]
        lines = StatementMoveLine.search([('invoice', 'in', invoice_ids)],
            limit=1)
        if lines:
            line, = lines
            raise UserError(gettext(
                'account_bank_statement_account.invoice_in_statement_move_line',
                    invoice=line.invoice.rec_name,
                    statement_line=line.line.rec_name))

        super(Invoice, cls).draft(invoices)
