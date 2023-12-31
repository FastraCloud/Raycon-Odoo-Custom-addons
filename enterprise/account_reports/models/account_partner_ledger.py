# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields
from odoo.tools.misc import formatLang
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime, timedelta


class ReportPartnerLedger(models.AbstractModel):
    _name = "account.partner.ledger"
    _description = "Partner Ledger"

    def _format(self, value):
        if self.env.context.get('no_format'):
            return value
        currency_id = self.env.user.company_id.currency_id
        if currency_id.is_zero(value):
            # don't print -0.0 in reports
            value = abs(value)
        res = formatLang(self.env, value, currency_obj=currency_id)
        return res

    @api.model
    def get_lines(self, context_id, line_id=None):
        if type(context_id) == int:
            context_id = self.env['account.partner.ledger.context'].search([['id', '=', context_id]])
        new_context = dict(self.env.context)
        account_types = []
        if 'receivable' in context_id.account_type:
            account_types.append('receivable')
        if 'payable' in context_id.account_type:
            account_types.append('payable')
        new_context.update({
            'date_from': context_id.date_from,
            'date_to': context_id.date_to,
            'state': context_id.all_entries and 'all' or 'posted',
            'cash_basis': context_id.cash_basis,
            'context_id': context_id,
            'company_ids': context_id.company_ids.ids,
            'account_types': account_types
        })
        return self.with_context(new_context)._lines(line_id)

    def do_query(self, line_id):
        # Create the currency table.
        user_company = self.env.user.company_id
        companies = self.env['res.company'].search([])
        rates_table_entries = []
        for company in companies:
            if company.currency_id == user_company.currency_id:
                rate = 1.0
            else:
                rate = user_company.currency_id.rate / company.currency_id.rate
            rates_table_entries.append((company.id, rate, user_company.currency_id.decimal_places))
        currency_table = ','.join('(%s, %s, %s)' % r for r in rates_table_entries)
        with_currency_table = 'WITH currency_table(company_id, rate, precision) AS (VALUES %s)' % currency_table

        # Sum query
        debit_field = 'debit_cash_basis' if self.env.context.get('cash_basis') else 'debit'
        credit_field = 'credit_cash_basis' if self.env.context.get('cash_basis') else 'credit'
        balance_field = 'balance_cash_basis' if self.env.context.get('cash_basis') else 'balance'
        tables, where_clause, params = self.env['account.move.line']._query_get(
            [('account_id.internal_type', 'in', self.env.context['account_types'])])
        query = '''
            SELECT
                \"account_move_line\".partner_id,
                SUM(ROUND(\"account_move_line\".''' + debit_field + ''' * currency_table.rate, currency_table.precision))     AS debit,
                SUM(ROUND(\"account_move_line\".''' + credit_field + ''' * currency_table.rate, currency_table.precision))    AS credit,
                SUM(ROUND(\"account_move_line\".''' + balance_field + ''' * currency_table.rate, currency_table.precision))   AS balance
            FROM %s
            LEFT JOIN currency_table                    ON currency_table.company_id = \"account_move_line\".company_id
            WHERE %s
            AND \"account_move_line\".partner_id IS NOT NULL
            GROUP BY \"account_move_line\".partner_id
        ''' % (tables, where_clause)
        if line_id:
            query = query.replace('WHERE', 'WHERE \"account_move_line\".partner_id = %s AND ')
            params = [str(line_id)] + params
        self._cr.execute(with_currency_table + query, params)
        query_res = self._cr.dictfetchall()
        return dict((res['partner_id'], res) for res in query_res)

    def group_by_partner_id(self, line_id):
        partners = {}
        results = self.do_query(line_id)
        initial_bal_date_to = datetime.strptime(self.env.context['date_from_aml'], DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=-1)
        initial_bal_results = self.with_context(date_to=initial_bal_date_to.strftime(DEFAULT_SERVER_DATE_FORMAT)).do_query(line_id)
        context = self.env.context
        base_domain = [('date', '<=', context['date_to']), ('company_id', 'in', context['company_ids']), ('account_id.internal_type', 'in', self.env.context['account_types'])]
        if context['date_from_aml']:
            base_domain.append(('date', '>=', context['date_from_aml']))
        if context['state'] == 'posted':
            base_domain.append(('move_id.state', '=', 'posted'))
        for partner_id, result in results.items():
            domain = list(base_domain)  # copying the base domain
            domain.append(('partner_id', '=', partner_id))
            partner = self.env['res.partner'].browse(partner_id)
            partners[partner] = result
            partners[partner]['initial_bal'] = initial_bal_results.get(partner.id, {'balance': 0, 'debit': 0, 'credit': 0})
            partners[partner]['lines'] = self.env['account.move.line'].search(domain, order='date')
        return partners

    @api.model
    def _lines(self, line_id=None):
        lines = []
        context = self.env.context
        company_id = context.get('company_id') or self.env.user.company_id
        grouped_partners = self.with_context(date_from_aml=context['date_from'], date_from=context['date_from'] and company_id.compute_fiscalyear_dates(datetime.strptime(context['date_from'], DEFAULT_SERVER_DATE_FORMAT))['date_from'] or None).group_by_partner_id(line_id)  # Aml go back to the beginning of the user chosen range but the amount on the partner line should go back to either the beginning of the fy or the beginning of times depending on the partner
        sorted_partners = sorted(grouped_partners, key=lambda p: p.name)
        unfold_all = context.get('print_mode') and not context['context_id']['unfolded_partners']
        for partner in sorted_partners:
            debit = grouped_partners[partner]['debit']
            credit = grouped_partners[partner]['credit']
            balance = grouped_partners[partner]['balance']
            lines.append({
                'id': partner.id,
                'type': 'line',
                'name': partner.name,
                'footnotes': self.env.context['context_id']._get_footnotes('line', partner.id),
                'columns': [self._format(debit), self._format(credit), self._format(balance)],
                'level': 2,
                'unfoldable': True,
                'unfolded': partner in context['context_id']['unfolded_partners'] or unfold_all,
                'colspan': 5,
            })
            unfold_partners = context['context_id'].with_context(active_test=False)['unfolded_partners']
            used_currency = company_id.currency_id
            if partner in unfold_partners or unfold_all:
                progress = grouped_partners[partner]['initial_bal']['balance']
                domain_lines = []
                amls = amls_all = grouped_partners[partner]['lines']
                too_many = False
                if len(amls) > 80 and not context.get('print_mode'):
                    amls = amls[-80:]
                    too_many = True
                for line in amls:
                    if self.env.context['cash_basis']:
                        line_debit = line.debit_cash_basis
                        line_credit = line.credit_cash_basis
                    else:
                        line_debit = line.debit
                        line_credit = line.credit
                    line_currency = line.company_id.currency_id.with_context(date=amls.env.context.get('date') or fields.Date.today())
                    line_debit = line_currency.compute(line_debit, used_currency)
                    line_credit = line_currency.compute(line_credit, used_currency)
                    progress = progress + line_debit - line_credit
                    name = []
                    name = '-'.join(
                        (line.move_id.name not in ['', '/'] and [line.move_id.name] or []) +
                        (line.ref not in ['', '/', False] and [line.ref] or []) +
                        (line.name not in ['', '/'] and [line.name] or [])
                    )
                    if len(name) > 35 and not self.env.context.get('no_format'):
                        name = name[:32] + "..."
                    domain_lines.append({
                        'id': line.id,
                        'type': 'move_line_id',
                        'move_id': line.move_id.id,
                        'action': line.get_model_id_and_name(),
                        'name': line.date,
                        'footnotes': self.env.context['context_id']._get_footnotes('move_line_id', line.id),
                        'columns': [line.journal_id.code, line.account_id.code, name, line.full_reconcile_id.name,
                                    line_debit != 0 and self._format(line_debit) or '',
                                    line_credit != 0 and self._format(line_credit) or '',
                                    self._format(progress)],
                        'level': 1,
                    })
                initial_debit = grouped_partners[partner]['initial_bal']['debit']
                initial_credit = grouped_partners[partner]['initial_bal']['credit']
                initial_balance = grouped_partners[partner]['initial_bal']['balance']
                domain_lines[:0] = [{
                    'id': partner.id,
                    'type': 'initial_balance',
                    'name': _('Initial Balance'),
                    'footnotes': self.env.context['context_id']._get_footnotes('initial_balance', partner.id),
                    'columns': ['', '', '', '', self._format(initial_debit), self._format(initial_credit), self._format(initial_balance)],
                    'level': 1,
                }]
                domain_lines.append({
                    'id': partner.id,
                    'type': 'o_account_reports_domain_total',
                    'name': _('Total') + ' ' + (partner.name or ''),
                    'footnotes': self.env.context['context_id']._get_footnotes('o_account_reports_domain_total', partner.id),
                    'columns': ['', '', '', '', self._format(debit), self._format(credit), self._format(balance)],
                    'level': 1,
                })
                if too_many:
                    domain_lines.append({
                        'id': partner.id,
                        'domain': "[('id', 'in', %s)]" % amls_all.ids,
                        'type': 'too_many_partners',
                        'name': _('There are more than 80 items in this list, click here to see all of them'),
                        'footnotes': {},
                        'colspan': 8,
                        'columns': [],
                        'level': 3,
                    })
                lines += domain_lines
        return lines

    @api.model
    def get_title(self):
        return _('Partner Ledger')

    @api.model
    def get_name(self):
        return 'partner_ledger'

    @api.model
    def get_report_type(self):
        return self.env.ref('account_reports.account_report_type_date_range_no_comparison')

    @api.model
    def get_template(self):
        return 'account_reports.report_financial'


class ReportPartnerLedgerContext(models.TransientModel):
    _name = "account.partner.ledger.context"
    _description = "A particular context for the Partner Ledger report"
    _inherit = "account.report.context.common"

    fold_field = 'unfolded_partners'
    unfolded_partners = fields.Many2many('res.partner', 'partner_ledger_to_partners', string='Unfolded lines')
    account_type = fields.Selection([('receivable', 'Receivable Accounts'),
                                     ('payable', 'Payable Accounts'),
                                     ('receivable_payable', 'Receivable and Payable Accounts')
                                    ], string="Account Type", default='receivable_payable')

    def get_report_obj(self):
        return self.env['account.partner.ledger']

    def get_columns_names(self):
        return [_('JRNL'), _('Account'), _('Ref'), _('Matching Number'), _('Debit'), _('Credit'), _('Balance')]

    @api.multi
    def get_columns_types(self):
        return ["text", "text", "text", "text", "number", "number", "number"]
