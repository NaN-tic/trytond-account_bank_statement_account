from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta

__all__ = ['Invoice']


class Invoice:
    __name__ = 'account.invoice'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'invoice_in_statement_move_line': ('Invoice "%(invoice)s" '
                    'cannot be moved to "Draft" state because it is already '
                    'used in statement line "%(statement_line)s".'),
                })

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
            cls.raise_user_error('invoice_in_statement_move_line', {
                    'invoice': line.invoice.rec_name,
                    'statement_line': line.line.rec_name,
                    })
        super(Invoice, cls).draft(invoices)


