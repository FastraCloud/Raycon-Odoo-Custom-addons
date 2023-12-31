# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, _
from odoo.exceptions import UserError
import calendar
import time
from itertools import groupby


class AccountFinancialReportXMLExport(models.AbstractModel):
    _inherit = "account.financial.html.report.xml.export"

    @api.model
    def is_xml_export_available(self, report_obj):
        if report_obj._name == 'l10n.be.report.partner.vat.listing' or report_obj._name == 'l10n.be.report.partner.vat.intra' or (report_obj._name == 'account.financial.html.report' and report_obj.id == self.env['ir.model.data'].xmlid_to_res_id('l10n_be_reports.account_financial_report_l10n_be_tva0')):
            return True
        else:
            return super(AccountFinancialReportXMLExport, self).is_xml_export_available(report_obj)

    def do_xml_export(self, context):
        if context.get_report_obj()._name == 'account.financial.html.report' and context.get_report_obj().id == self.env['ir.model.data'].xmlid_to_res_id('l10n_be_reports.account_financial_report_l10n_be_tva0'):
            return self._l10n_be_vat_export(context)
        if context.get_report_obj()._name == 'l10n.be.report.partner.vat.listing':
            return self._l10n_be_partner_vat_export(context)
        if context.get_report_obj()._name == 'l10n.be.report.partner.vat.intra':
            return self._l10n_be_partner_vat_intra_export(context)
        else:
            return super(AccountFinancialReportXMLExport, self).do_xml_export(context)

    @api.model
    def check(self, report_name, report_id=None):
        if report_name == 'account.financial.html.report' and report_id == self.env['ir.model.data'].xmlid_to_res_id('l10n_be_reports.account_financial_report_l10n_be_tva0'):
            company = self.env.user.company_id
            vat_no = company.partner_id.vat
            if not vat_no:
                return _('No VAT number associated with your company.')
            default_address = company.partner_id.address_get()
            address = self.env['res.partner'].browse(default_address.get("default")) or company.partner_id
            if not address.email:
                return _('No email address associated with the company.')
            if not address.phone:
                return _('No phone associated with the company.')
            return True
        if report_name == 'l10n.be.report.partner.vat.listing':
            company = self.env.user.company_id
            vat_no = company.partner_id.vat
            if not vat_no:
                return _('No VAT number associated with your company.')
            default_address = company.partner_id.address_get()
            address = default_address.get('invoice', company.partner_id)
            if not address.email:
                return _('No email address associated with the company.')
            if not address.phone:
                return _('No phone associated with the company.')
            return True
        if report_name == 'l10n.be.report.partner.vat.intra':
            company = self.env.user.company_id
            vat_no = company.partner_id.vat
            if not vat_no:
                return _('No VAT number associated with your company.')
            default_address = company.partner_id.address_get()
            address = default_address.get('invoice', company.partner_id)
            if not address.email:
                return _('No email address associated with the company.')
            if not address.phone:
                return _('No phone associated with the company.')
            return True
        else:
            return super(AccountFinancialReportXMLExport, self).check(report_name, report_id)

    def _l10n_be_partner_vat_intra_export(self, context):
        post_code = street = city = country = data_clientinfo = ''

        company = self.env.user.company_id
        company_vat = company.partner_id.vat
        company_vat = company_vat.replace(' ', '').upper()
        issued_by = company_vat[:2]

        seq_declarantnum = self.env['ir.sequence'].get('declarantnum')
        dnum = company_vat[2:] + seq_declarantnum[-4:]

        addr = company.partner_id.address_get(['invoice'])
        if addr.get('invoice', False):
            ads = self.env['res.partner'].browse([addr['invoice']])[0]
            phone = ads.phone and ads.phone.replace(' ', '') or ''
            email = ads.email or ''
            city = ads.city or ''
            post_code = ads.zip or ''
            if not city:
                city = ''
            if ads.street:
                street = ads.street
            if ads.street2:
                street += ' ' + ads.street2
            if ads.country_id:
                country = ads.country_id.code

        if not country:
            country = company_vat[:2]

        date_from = context.date_from[0:7] + '-01'
        date_to = context.date_from[0:7] + '-31'

        ctx_date_from = context.date_from[5:10]
        ctx_date_to = context.date_to[5:10]
        month = None
        quarter = None
        if ctx_date_from == '01-01' and ctx_date_to == '03-31':
            quarter = '1'
        elif ctx_date_from == '04-01' and ctx_date_to == '06-30':
            quarter = '2'
        elif ctx_date_from == '07-01' and ctx_date_to == '09-30':
            quarter = '3'
        elif ctx_date_from == '10-01' and ctx_date_to == '12-31':
            quarter = '4'
        elif ctx_date_from != '01-01' or ctx_date_to != '12-31':
            month = context.date_from[5:7]

        xml_data = context.get_report_obj().with_context(no_format=True, date_from=date_from, date_to=date_to).get_lines(context, get_xml_data=True)
        xml_data.update({
            'company_name': company.name,
            'company_vat': company_vat,
            'vatnum': company_vat[2:],
            'sender_date': str(time.strftime('%Y-%m-%d')),
            'street': street,
            'city': city,
            'post_code': post_code,
            'country': country,
            'email': email,
            'phone': phone.replace('/', '').replace('.', '').replace('(', '').replace(')', '').replace(' ', ''),
            'year': context.date_from[0:4],
            'month': month,
            'quarter': quarter,
            'comments': context.summary or '',
            'issued_by': issued_by,
            'dnum': dnum,
        })

        data_head = """<?xml version="1.0" encoding="ISO-8859-1"?>
<ns2:IntraConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/IntraConsignment" IntraListingsNbr="1">"""
        data_comp_period = '\n\t\t<ns2:Declarant>\n\t\t\t<VATNumber>%(vatnum)s</VATNumber>\n\t\t\t<Name>%(company_name)s</Name>\n\t\t\t<Street>%(street)s</Street>\n\t\t\t<PostCode>%(post_code)s</PostCode>\n\t\t\t<City>%(city)s</City>\n\t\t\t<CountryCode>%(country)s</CountryCode>\n\t\t\t<EmailAddress>%(email)s</EmailAddress>\n\t\t\t<Phone>%(phone)s</Phone>\n\t\t</ns2:Declarant>'
        data_comp_period += '\n\t\t<ns2:Period>\n'
        if month:
            data_comp_period += '\t\t\t<ns2:Month>%(month)s</ns2:Month>\n'
        elif quarter:
            data_comp_period += '\t\t\t<ns2:Quarter>%(quarter)s</ns2:Quarter>\n'
        data_comp_period += '\t\t\t<ns2:Year>%(year)s</ns2:Year>\n\t\t</ns2:Period>'
        data_comp_period %= xml_data

        data_clientinfo = ''
        seq = 0
        for line in xml_data['lines']:
            seq += 1
            vat = line['columns'][0]
            if not vat:
                raise UserError(_('No vat number defined for %s.') % line['name'])
            client = {
                'partner_name': line['name'],
                'vatnum': vat[2:].replace(' ', '').upper(),
                'vat': vat,
                'country': vat[:2],
                'amount': line['columns'][3] or 0.0,
                'intra_code': line['columns'][2],
                'code': line['columns'][1],
                'seq': seq,
            }
            data_clientinfo += '\n\t\t<ns2:IntraClient SequenceNumber="%(seq)s">\n\t\t\t<ns2:CompanyVATNumber issuedBy="%(country)s">%(vatnum)s</ns2:CompanyVATNumber>\n\t\t\t<ns2:Code>%(code)s</ns2:Code>\n\t\t\t<ns2:Amount>%(amount).2f</ns2:Amount>\n\t\t</ns2:IntraClient>' % (client)

        data_decl = '\n\t<ns2:IntraListing SequenceNumber="1" ClientsNbr="%(clientnbr)s" DeclarantReference="%(dnum)s" AmountSum="%(amountsum).2f">' % (xml_data)

        return data_head + data_decl + data_comp_period + data_clientinfo + '\n\t\t</ns2:IntraListing>\n</ns2:IntraConsignment>' % (xml_data)

    def _l10n_be_partner_vat_export(self, context):
        seq_declarantnum = self.env['ir.sequence'].get('declarantnum')
        company = self.env.user.company_id
        company_vat = company.partner_id.vat

        company_vat = company_vat.replace(' ', '').upper()
        SenderId = company_vat[2:]
        issued_by = company_vat[:2]
        dnum = company_vat[2:] + seq_declarantnum[-4:]
        street = city = country = ''
        addr = company.partner_id.address_get(['invoice'])
        if addr.get('invoice', False):
            ads = self.env['res.partner'].browse([addr['invoice']])[0]
            phone = ads.phone and ads.phone.replace(' ', '') or ''
            email = ads.email or ''
            city = ads.city or ''
            zip = ads.zip or ''
            if not city:
                city = ''
            if ads.street:
                street = ads.street
            if ads.street2:
                street += ' ' + ads.street2
            if ads.country_id:
                country = ads.country_id.code

        annual_listing_data = {
            'issued_by': issued_by,
            'company_vat': company_vat,
            'comp_name': company.name,
            'street': street,
            'zip': zip,
            'city': city,
            'country': country,
            'email': email,
            'phone': phone,
            'SenderId': SenderId,
            'period': context.date_from[0:4],
            'comments': context.summary or '',
        }

        data_file = """<?xml version="1.0" encoding="ISO-8859-1"?>
<ns2:ClientListingConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/ClientListingConsignment" ClientListingsNbr="1">
    <ns2:Representative>
        <RepresentativeID identificationType="NVAT" issuedBy="%(issued_by)s">%(SenderId)s</RepresentativeID>
        <Name>%(comp_name)s</Name>
        <Street>%(street)s</Street>
        <PostCode>%(zip)s</PostCode>
        <City>%(city)s</City>"""
        if annual_listing_data['country']:
            data_file += "\n\t\t<CountryCode>%(country)s</CountryCode>"
        data_file += """
        <EmailAddress>%(email)s</EmailAddress>
        <Phone>%(phone)s</Phone>
    </ns2:Representative>"""
        data_file = data_file % annual_listing_data

        data_comp = """
        <ns2:Declarant>
            <VATNumber>%(SenderId)s</VATNumber>
            <Name>%(comp_name)s</Name>
            <Street>%(street)s</Street>
            <PostCode>%(zip)s</PostCode>
            <City>%(city)s</City>
            <CountryCode>%(country)s</CountryCode>
            <EmailAddress>%(email)s</EmailAddress>
            <Phone>%(phone)s</Phone>
        </ns2:Declarant>
        <ns2:Period>%(period)s</ns2:Period>
        """ % annual_listing_data

        # Turnover and Farmer tags are not included
        date_from = context.date_from[0:4] + '-01-01'
        date_to = context.date_from[0:4] + '-12-31'
        lines = context.get_report_obj().with_context(no_format=True, date_from=date_from, date_to=date_to).get_lines(context)

        data_client_info = ''
        seq = 0
        sum_turnover = 0.00
        sum_tax = 0.00
        lines = sorted(lines, key=lambda l: l['columns'][0])
        for vat, values in groupby(lines, key=lambda l: l['columns'][0]):
            values = list(values)
            turnover = sum([k['columns'][1] or 0.0 for k in values])
            tax = sum([k['columns'][2] or 0.0 for k in values])
            seq += 1
            sum_turnover += turnover
            sum_tax += tax
            amount_data = {
                'seq': str(seq),
                'only_vat': vat[2:],
                'turnover': turnover,
                'vat_amount': tax,
            }
            data_client_info += """
        <ns2:Client SequenceNumber="%(seq)s">
            <ns2:CompanyVATNumber issuedBy="BE">%(only_vat)s</ns2:CompanyVATNumber>
            <ns2:TurnOver>%(turnover).2f</ns2:TurnOver>
            <ns2:VATAmount>%(vat_amount).2f</ns2:VATAmount>
        </ns2:Client>""" % amount_data

        amount_data_begin = {
            'seq': str(seq),
            'dnum': dnum,
            'sum_turnover': sum_turnover,
            'sum_tax': sum_tax,
        }
        data_begin = """
    <ns2:ClientListing SequenceNumber="1" ClientsNbr="%(seq)s" DeclarantReference="%(dnum)s"
        TurnOverSum="%(sum_turnover).2f" VATAmountSum="%(sum_tax).2f">
""" % amount_data_begin

        data_end = """

        <ns2:Comment>%(comments)s</ns2:Comment>
    </ns2:ClientListing>
</ns2:ClientListingConsignment>
""" % annual_listing_data

        return data_file + data_begin + data_comp + data_client_info + data_end

    def _l10n_be_vat_export(self, context):
        list_of_tags = ['00', '01', '02', '03', '44', '45', '46', '47', '48', '49', '54', '55', '56', '57', '59', '61', '62', '63', '64', '71', '72', '81', '82', '83', '84', '85', '86', '87', '88', '91']
        company = self.env.user.company_id
        vat_no = company.partner_id.vat
        if not vat_no:
            raise UserError(_('No VAT number associated with your company.'))

        vat_no = vat_no.replace(' ', '').upper()

        default_address = company.partner_id.address_get()
        address = self.env['res.partner'].browse(default_address.get("default", company.partner_id.id))

        issued_by = vat_no[:2]

        send_ref = str(company.partner_id.id) + str(context.date_from[5:7]) + str(context.date_to[:4])
        starting_month = context.date_from[5:7]
        ending_month = context.date_to[5:7]
        quarter = str(((int(starting_month) - 1) / 3) + 1)

        date_from = context.date_from[0:7] + '-01'
        date_to = context.date_to[0:7] + '-' + str(calendar.monthrange(int(context.date_to[0:4]), int(ending_month))[1])
        lines = context.get_report_obj().with_context(no_format=True, date_from=date_from, date_to=date_to).get_lines(context)

        data = {'client_nihil': False, 'ask_restitution': False, 'ask_payment': False}

        if not address.email:
            raise UserError(_('No email address associated with the company.'))
        if not address.phone:
            raise UserError(_('No phone associated with the company.'))
        file_data = {
                        'issued_by': issued_by,
                        'vat_no': vat_no,
                        'only_vat': vat_no[2:],
                        'cmpny_name': company.name,
                        'address': "%s %s" % (address.street or "", address.street2 or ""),
                        'post_code': address.zip or "",
                        'city': address.city or "",
                        'country_code': address.country_id and address.country_id.code or "",
                        'email': address.email or "",
                        'phone': address.phone.replace('.', '').replace('/', '').replace('(', '').replace(')', '').replace(' ', ''),
                        'send_ref': send_ref,
                        'quarter': quarter,
                        'month': starting_month,
                        'year': str(context.date_to[:4]),
                        'client_nihil': (data['client_nihil'] and 'YES' or 'NO'),
                        'ask_restitution': (data['ask_restitution'] and 'YES' or 'NO'),
                        'ask_payment': (data['ask_payment'] and 'YES' or 'NO'),
                        'comments': context.summary or '',
                     }

        data_of_file = """<?xml version="1.0"?>
<ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
    <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%(send_ref)s">
        <ns2:Declarant>
            <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">%(only_vat)s</VATNumber>
            <Name>%(cmpny_name)s</Name>
            <Street>%(address)s</Street>
            <PostCode>%(post_code)s</PostCode>
            <City>%(city)s</City>
            <CountryCode>%(country_code)s</CountryCode>
            <EmailAddress>%(email)s</EmailAddress>
            <Phone>%(phone)s</Phone>
        </ns2:Declarant>
        <ns2:Period>
    """ % (file_data)

        if starting_month != ending_month:
            # starting month and ending month of selected period are not the same
            # it means that the accounting isn't based on periods of 1 month but on quarters
            data_of_file += '\t\t<ns2:Quarter>%(quarter)s</ns2:Quarter>\n\t\t' % (file_data)
        else:
            data_of_file += '\t\t<ns2:Month>%(month)s</ns2:Month>\n\t\t' % (file_data)
        data_of_file += '\t<ns2:Year>%(year)s</ns2:Year>' % (file_data)
        data_of_file += '\n\t\t</ns2:Period>\n'
        data_of_file += '\t\t<ns2:Data>\t'
        cases_list = []
        currency_id = self.env.user.company_id.currency_id
        for line in lines:
            if line['name'].startswith('91') and ending_month != 12:
                # the tax code 91 can only be send for the declaration of December
                continue
            if line['columns'][0] and not currency_id.is_zero(line['columns'][0]):
                for tag in list_of_tags:
                    if line['name'].startswith(tag):
                        tags_list = [x[0] for x in cases_list]
                        if tag in tags_list:
                            cases_list[tags_list.index(tag)] = (tag, cases_list[tags_list.index(tag)][1] + line['columns'][0])
                        else:
                            cases_list.append((tag, line['columns'][0]))
                        del tag
        cases_list = sorted(cases_list, key=lambda a: a[0])
        for item in cases_list:
            grid_amount_data = {
                    'code': str(int(item[0])),
                    'amount': '%.2f' % abs(item[1]),
                    }
            data_of_file += '\n\t\t\t<ns2:Amount GridNumber="%(code)s">%(amount)s</ns2:Amount''>' % (grid_amount_data)

        data_of_file += '\n\t\t</ns2:Data>'
        data_of_file += '\n\t\t<ns2:ClientListingNihil>%(client_nihil)s</ns2:ClientListingNihil>' % (file_data)
        data_of_file += '\n\t\t<ns2:Ask Restitution="%(ask_restitution)s" Payment="%(ask_payment)s"/>' % (file_data)
        data_of_file += '\n\t\t<ns2:Comment>%(comments)s</ns2:Comment>' % (file_data)
        data_of_file += '\n\t</ns2:VATDeclaration> \n</ns2:VATConsignment>'

        return data_of_file
