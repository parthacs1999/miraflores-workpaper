"""Independent printed-source checks plus explicitly labelled engine consistency checks."""
import re
from decimal import Decimal
from functools import lru_cache

from app.services.packet_service import load_packet
from app.services.reconciliation_core import AMOUNT, Rule, Context, Unsupported, ConflictingSources, decimal, execute


def receipts(c):
    books = c.amount('D14', r'Total income ' + AMOUNT, 'Book gross receipts')
    card = c.amount('D15', AMOUNT + r' arrived through Paywell', 'Card receipts already in deposits', 3)
    form = c.amount('D21', r'Box 1a gross amount[^\d]+' + AMOUNT, '1099-K receipts')
    if card != form:
        raise ConflictingSources('Deposit reconciliation and Form 1099-K disagree; do not assume the duplicate amount.')
    c.require_text('D15', 'Client deposits are recorded as Sales - client projects', 3)
    c.step('1099-K is corroboration, not incremental income; already-booked card receipts', card)
    return c.step('Books income plus unmatched card receipts (zero established by deposit detail)', books)


def expense(c, item):
    if item == 'software':
        books = c.amount('D14', r'Software and subscriptions ' + AMOUNT, 'Books software')
        personal = c.amount('D15', r'Spotify Family ' + AMOUNT, 'Personal software included in books')
        notes = c.record('call-01', ('notes',))
        if not any('Spotify Family' in n and 'personal' in n for n in notes):
            raise Unsupported('Business/personal classification is not substantiated by the client call.')
        return c.step('Books software less client-identified personal subscription', books-personal)
    if item == 'utilities':
        phone = c.amount('D14', r'Telephone ' + AMOUNT, 'Books family telephone')
        internet = c.amount('D14', r'Internet ' + AMOUNT, 'Books shared internet')
        notes = c.record('call-01', ('notes',))
        def percentage(word):
            found = [decimal(m[1])/100 for n in notes if word in n.lower() for m in re.finditer(r'(\d+)%', n)]
            if len(found) != 1:
                raise Unsupported('Missing or ambiguous client business-use percentage for ' + word)
            return found[0]
        return c.step('Client-estimated business shares: telephone × mobile percentage + internet × internet percentage', phone*percentage('mobile') + internet*percentage('internet'))
    if item == 'meals':
        books = c.amount('D14', r'Meals ' + AMOUNT, 'Books meals')
        c.record('call-01', ('notes',))
        if 'R-MEALS-50' not in c.packet['engine_reference']['rules']:
            raise Unsupported('Packet meals deduction rule is absent.')
        return c.step('Packet R-MEALS-50: business meals × 50%', books*Decimal('.5'))
    raise Unsupported('Unknown expense rule.')


def conditional_books_bridge(c):
    net=c.amount('D14',r'Net income '+AMOUNT,'Books net income')
    gross=c.amount('D14',r'Total income '+AMOUNT,'Books total income')
    expense_total=c.amount('D14',r'Total expenses '+AMOUNT,'Books total expenses')
    if gross-expense_total!=net:
        raise ConflictingSources('Printed P&L totals do not reconcile.')
    fuel=c.amount('D14',r'Car and truck - fuel '+AMOUNT,'Books fuel expense')
    book_depreciation=c.amount('D14',r'Depreciation '+AMOUNT,'Books depreciation')
    health=c.amount('D14',r'Insurance - health \(Erik\) '+AMOUNT,'Books health insurance; exclude from Schedule C expenses')
    software_books=c.amount('D14',r'Software and subscriptions '+AMOUNT,'Books software')
    utilities_books=c.amount('D14',r'Telephone '+AMOUNT,'Books telephone')+c.amount('D14',r'Internet '+AMOUNT,'Books internet')
    meals_books=c.amount('D14',r'Meals '+AMOUNT,'Books meals')
    software_adjustment=software_books-expense(c,'software')
    utilities_adjustment=utilities_books-expense(c,'utilities')
    meals_adjustment=meals_books-expense(c,'meals')
    # These are explicitly selected/supplied engine amounts, not independently proved elections.
    selected_depreciation=c.line('SchC.13')
    selected_home_office=c.line('SchC.30')
    return c.step('Conditional bridge: book profit + book fuel + book depreciation + book health premiums + personal software/utilities + nondeductible meals − unique mileage deduction − supplied tax depreciation − supplied home office',
        net+fuel+book_depreciation+health+software_adjustment+utilities_adjustment+meals_adjustment-vehicle(c)-selected_depreciation-selected_home_office)


def unique_miles(c):
    pages = c.documents.get('D23', {}).get('pages', [])
    if not pages:
        raise Unsupported('Mileage log is missing.')
    seen, total = set(), Decimal(0)
    for page in pages:
        text = page['printed_content']
        normalized = ' '.join(re.sub(r'^\(Second scan.*?\)\s*', '', text).split())
        if normalized in seen:
            c.input('Excluded duplicate mileage page', text, f"doc:D23#page{page['page']}", 'duplicate_page')
            continue
        seen.add(normalized)
        trips = list(re.finditer(r'\b\d{4}-\d{2}-\d{2}\s+[^;]+?\s(\d+) mi\b', text))
        if not trips:
            raise Unsupported(f"No attributable trip mile entries on D23 page {page['page']}")
        for match in trips:
            miles = decimal(match[1])
            c.input('Trip miles', miles, f"doc:D23#page{page['page']}", 'printed_source', {'start': match.start(1), 'end': match.end(1)}, match[0])
            total += miles
    return c.step('Sum each printed trip once, excluding the explicitly duplicated sheet', total)


def vehicle(c):
    return c.step('Unique business miles × packet mileage rate; books fuel is not added', unique_miles(c)*c.param('mileage_rate'))


def printed_lots(c, doc):
    document = c.documents.get(doc)
    if not document:
        raise Unsupported('Brokerage document missing: ' + doc)
    lots = {}
    pattern = r'\b([NMX]\d+)\s+([^;]*?)\bacquired\s+(\d{4}-\d{2}-\d{2})\s+sold\s+(\d{4}-\d{2}-\d{2})\s+proceeds\s+' + AMOUNT + r'\s+basis\s+(\(?not reported\)?|\d[\d,]*(?:\.\d+)?)(?:\s+wash sale loss disallowed\s+' + AMOUNT + r')?'
    for page in document['pages']:
        for match in re.finditer(pattern, page['printed_content'], re.I):
            key = match[1]
            if key in lots:
                raise ConflictingSources('Repeated lot identifier in selected source: ' + key)
            lots[key] = {'id': key, 'description': match[2], 'acquired': match[3], 'sold': match[4],
                         'proceeds': decimal(match[5]), 'basis': None if match[6].lower().strip('()') == 'not reported' else decimal(match[6]),
                         'wash': decimal(match[7]) if match[7] is not None else Decimal(0),
                         'ref': f"doc:{doc}#page{page['page']}", 'raw': match[0], 'start': match.start(), 'end': match.end()}
    if not lots:
        raise Unsupported('Printed brokerage lot format is not supported; no totals inferred.')
    return lots


def meridian_summary(c):
    doc = 'D31' if 'D30' in c.version.get('documents_superseded', []) else 'D30'
    summary = c.amount(doc, r'total proceeds ' + AMOUNT, 'Broker proceeds summary')
    lots = printed_lots(c, doc)
    for lot in lots.values():
        c.input(lot['id'] + ' printed proceeds', lot['proceeds'], lot['ref'], 'printed_source', raw=lot['raw'])
    total = c.step('Sum all printed transaction proceeds, including unextracted supplemental page', sum(l['proceeds'] for l in lots.values()))
    if total != summary:
        raise ConflictingSources('Printed summary and printed detail disagree; no authoritative brokerage total can be assumed.')
    extracted = [e for e in c.packet['extracted_values'] if e['document_id'] == doc and e['field'].endswith('_proceeds') and re.match(r'M\d+_', e['field'])]
    if not extracted:
        raise Unsupported('Extracted lot proceeds are missing.')
    for value in extracted:
        c.input('Pipeline lot proceeds '+value['field'],decimal(value['value']),value['id'],'pipeline_extracted',raw=value.get('text_as_read'))
    c.step('Extracted detail total (for comparison with printed summary)', sum(decimal(e['value']) for e in extracted))
    # Target is synthetic comparison, explicitly supplied in rule factory below.
    c.comparison_reported = sum(decimal(e['value']) for e in extracted)
    return total


def lot_expected(c, doc, lot_id):
    lot = printed_lots(c, doc).get(lot_id)
    if lot is None:
        raise Unsupported('Printed transaction is missing: ' + lot_id)
    c.input('Printed lot', lot['raw'], lot['ref'], 'printed_source', {'start': lot['start'], 'end': lot['end']}, lot['raw'])
    basis = lot['basis']
    if doc == 'D28' and lot_id in {'N1', 'N3', 'N4', 'N2'}:
        # Supplemental basis is attributable by unique sale/acquisition dates, not by confidence scores.
        supplement = c.text('D11',2)
        if lot_id == 'N2':
            pattern = r'ESPP.*?adjusted basis ' + AMOUNT
        else:
            pattern = r'acquired\s+' + lot['acquired'][5:7] + '/' + lot['acquired'][8:] + '/' + lot['acquired'][:4] + r'.*?adjusted basis ' + AMOUNT
        matches = list(re.finditer(pattern, supplement, re.I))
        if len(matches) != 1:
            raise Unsupported('A unique stock compensation supplemental basis was not located for ' + lot_id)
        basis = c.input('Supplemental adjusted basis', decimal(matches[0][1]), 'doc:D11#page2', 'printed_source', raw=matches[0][0])
    if basis is None:
        raise Unsupported('Cost basis is absent; zero cannot be substituted for an unknown basis.')
    return c.step('Printed proceeds − corroborated basis + printed wash-sale adjustment', lot['proceeds']-basis+lot['wash'])


def crypto_basis(c):
    c.record('msg-07')
    raise Unsupported('Client describes an approximate crypto basis and acquisition date, but the referenced bank statement is not in the packet. Basis/holding period require substantiation; no zero or approximate basis is treated as proven.')


def prior_accum(c, asset_id, jurisdiction):
    records = c.record('py:/asset_records')
    prior = next((a for a in records if a['asset_id'] == asset_id), None)
    if not prior:
        raise Unsupported('Prior asset depreciation record is missing.')
    history = prior.get(jurisdiction)
    if not history:
        raise Unsupported('Prior jurisdiction depreciation history is missing.')
    return c.step('Sum prior-year per-asset depreciation records (not current engine accumulated basis)', sum(decimal(v) for v in history.values()))


def asset_roll(c, asset_id, jurisdiction):
    prior = prior_accum(c, asset_id, jurisdiction)
    c.comparison_reported = c.number('asset:' + asset_id, (jurisdiction, 'prior_accumulated'))
    return prior


def sale(c):
    price = c.amount('D51', r'Contract sales price ' + AMOUNT, 'Gross sales price')
    commission = c.amount('D51', r'broker commissions ' + AMOUNT, 'Selling commissions')
    fees = c.amount('D51', r'title policy and escrow fees ' + AMOUNT, 'Selling fees')
    cost = c.amount('D51', r'Original purchase.*? for ' + AMOUNT, 'Original property cost including land', 2)
    flooring = c.amount('D51', r'Flooring replaced.*? for ' + AMOUNT, 'Capitalized flooring cost', 2)
    # Current-year depreciation is engine-supplied; this check is expressly conditional on it.
    dep = sum(prior_accum(c, a, 'federal') + c.number('asset:'+a, ('federal','depreciation_2025')) for a in ('AUS-BLDG','AUS-FLOOR'))
    return c.step('Gross price − selling costs − (property cost + flooring − supplied depreciation)', price-commission-fees-cost-flooring+dep)


def ca_wages(c):
    corvane = c.amount('D08', r'Box 16 ' + AMOUNT, 'Corvane CA wages')
    halvorsen = c.amount('D73', r'CA taxable wages ' + AMOUNT, 'Halvorsen resident-period CA wages')
    c.require_text('D73', 'Work location changed to Austin, TX effective 07/15/2025')
    return c.step('Corvane CA wages plus paystub-supported resident-period Halvorsen CA wages; payroll W-2 state allocation conflicts', corvane+halvorsen)


def interest(c):
    # Preserve the duplicate-form relationship at the payer/account level.
    sweep = c.amount('D28', r'box 1 interest ' + AMOUNT, 'Broker bank sweep interest')
    duplicate = c.amount('D29', r'Box 1 interest income ' + AMOUNT, 'Same bank-sweep payer/account')
    c.require_text('D29', 'account ending 7731')
    if sweep != duplicate:
        raise ConflictingSources('Duplicate bank sweep statements disagree.')
    c.comparison_reported = c.line('SchB.1.1') + c.line('SchB.1.2')
    return c.step('Same payer/account amount counted once, not once per form', sweep)


def mortgage(c):
    a = c.amount('D55', r'Box 1 mortgage interest received ' + AMOUNT, 'Original lender Form 1098 interest')
    b = c.amount('D57', r'Box 1 mortgage interest received ' + AMOUNT, 'Refinance lender Form 1098 interest')
    points = c.amount('D54', r'Origination points paid by buyer ' + AMOUNT, 'Purchase points')
    c.require_text('D56', 'Interest is reported on the 2025 Form 1098')
    return c.step('Distinct Forms 1098 interest plus purchase points; do not add payoff interest again', a+b+points)


def property_tax(c):
    paid = c.amount('D58', r'Total levy ' + AMOUNT, 'Property tax levy paid')
    credit = c.amount('D54', r'Seller credit for 2025 county taxes.*?: ' + AMOUNT, 'Seller pre-purchase tax credit')
    return c.step('Home property tax paid less seller reimbursement for pre-purchase period; allocation requires CPA confirmation', paid-credit)


def salt_limit(c):
    base = c.line('SchA.5d')
    agi = c.line('F1040.11')
    cap = max(c.param('salt_cap_floor'), c.param('salt_cap')-max(Decimal(0),agi-c.param('salt_cap_phase_start'))*c.param('salt_cap_phase_rate'))
    return c.step('Packet SALT cap/phaseout applied to reported inputs only; corrected MAGI is not recomputed', min(base,cap))


def federal_estimates(c):
    snapshots = c.record('agency:/irs_account_transcript_2025')
    eligible = [s for s in snapshots if s['as_of'] <= c.version['computed_at'][:10]]
    if not eligible:
        raise Unsupported('No pre-computation IRS account snapshot exists.')
    snapshot = max(eligible, key=lambda s:s['as_of'])
    payments = [t for t in snapshot['transactions'] if t['code']=='670' and 'Estimated tax payment' == t['description']]
    if not payments:
        raise Unsupported('No attributable 2025 estimated-payment postings in IRS snapshot.')
    return c.step('Sum estimated-tax postings in latest available pre-computation IRS transcript; exclude extension and scripted post-filing amounts', sum(decimal(t['amount']) for t in payments))


def state_estimates(c):
    payments = c.record('agency:/ftb_account/tax_year_2025_payments')
    if not payments:
        raise Unsupported('No FTB tax-year-specific payment record.')
    return c.step('Sum only payments designated tax year 2025; the September 2024 credit is excluded', sum(decimal(t['amount']) for t in payments))


def withholding(c, box):
    return c.step('Sum distinct employer W-2 boxes; exclude duplicate phone image D10', sum(c.amount(doc, r'Box '+box+r' '+AMOUNT, 'W-2 box '+box+' '+doc) for doc in ('D08','D09')))


def passive(c):
    rental = c.line('SchE.21A') + c.line('SchE.21B')
    prior = c.number('py:/carryovers_into_2025/passive_1450_fremont') + c.number('py:/carryovers_into_2025/passive_1200_barton_hills')
    return c.step('Reported current rental losses less prior suspended losses; consistency only, not independent allowance eligibility', rental-prior)


def basis(c):
    start = c.number('py:/basis_records/scorp_lindqvist_family_woodworks/0/ending_stock_basis')
    inc23 = c.amount('D40', r'Box 1 ordinary business income '+AMOUNT, '2023 K-1 income')
    dist23 = c.amount('D40', r'Box 16D distributions '+AMOUNT, '2023 K-1 distributions')
    inc24 = c.number('py:/basis_records/scorp_lindqvist_family_woodworks/2/k1_income')
    dist24 = c.number('py:/basis_records/scorp_lindqvist_family_woodworks/2/distributions')
    return c.step('Known 2022 stock basis + 2023/2024 income − distributions; missing other basis adjustments remain a CPA limitation', start+inc23-dist23+inc24-dist24)


def unsupported(message):
    def run(c):
        raise Unsupported(message)
    return run


def rules_for(packet, version):
    r = []
    def add(id,area,title,target,method,fn,**kwargs):
        defaults = {
            'business.books_bridge':('doc:D14#page1','call-01'),
            'investment.crypto_basis':('msg-07','D34','D35'),
            'depreciation.rates':('py:/asset_records','asset:STU-PRINTER'),
            'disposition.recapture':('doc:D51#page1','asset:AUS-BLDG','asset:AUS-FLOOR'),
            'rental.hvac':('doc:D46#page1','doc:D47#page1','call-01'),
            'california.amt':('doc:D12#page1','F540NR.61'),
            'california.capital_sourcing':('D11','D34','household:ngozi'),
            'deductions.cash_gift':('doc:D64#page1','msg-08'),
            'carryover.outgoing':('py:/carryovers_into_2025',),
            'k1.outside_basis':('py:/basis_records/partnership_ridgeline',),
        }
        kwargs.setdefault('evidence_refs',defaults.get(id,()))
        r.append(Rule(id,area,title,target,method,fn,**kwargs))
    add('business.receipts','business','Duplicated card receipts','SchC.1','Reconcile printed P&L total to deposit detail and Form 1099-K; count matched card receipts once.',receipts)
    add('business.software','business','Personal software in business expenses','SchC.27a.1','Books software less the client-identified personal Spotify charge.',lambda c:expense(c,'software'),judgment=True)
    add('business.utilities','business','Telephone and internet business shares','SchC.25','Apply only the percentages expressly documented in call-01; these remain client estimates.',lambda c:expense(c,'utilities'),judgment=True)
    add('business.meals','business','Business meals books-to-tax','SchC.24b','Apply supplied R-MEALS-50 to printed business-meal expense.',lambda c:expense(c,'meals'))
    add('business.conditional_bridge','business','Conditional books-to-tax profit bridge','SchC.31','Bridge printed book profit using documented expense adjustments, unique mileage and explicitly supplied current tax depreciation/home office. Not a final corrected tax result.',conditional_books_bridge,judgment=True)
    add('business.books_bridge','business','Complete corrected books-to-tax profit bridge', 'SchC.31','Complete bridge is not asserted until expense allocations, cost-recovery elections and limits are resolved.',unsupported('Full corrected profit depends on CPA expense classifications and depreciation/retirement choices. Individual adjustments are shown separately.'))
    add('vehicle.miles','vehicle','Duplicate mileage sheet','SchC.44a','Sum printed trip mileage after excluding the explicitly repeated sheet.',unique_miles,unit='miles')
    add('vehicle.deduction','vehicle','Standard mileage deduction','SchC.9','Unique printed trip miles multiplied by supplied mileage_rate.',vehicle)
    add('investment.bank_sweep','investments','Duplicate bank-sweep interest',None,'Compare duplicated payer/account statements against their combined return inclusion.',interest)
    add('investment.meridian_summary','investments','Broker summary versus extracted detail',None,'Compare printed summary and all printed lots to the extracted transaction inventory.',meridian_summary)
    add('investment.crypto_basis','investments','Unsubstantiated crypto basis','SchD.3','Separate approximate client claims from documentary proof.',crypto_basis)
    selected_doc = 'D31' if 'D30' in version.get('documents_superseded',[]) else 'D30'
    # Aggregate unsupported results remain even when no individual lot can be parsed.
    for doc in ('D28', selected_doc, 'D74'):
        try:
            lots = printed_lots(Context(packet,version),doc)
        except Unsupported:
            lots = {}
        if not lots:
            add('investment.inventory.'+doc,'investments',doc+' lot inventory',None,'Printed transaction inventory is required.',unsupported('Printed lot detail is missing or unsupported for '+doc),evidence_refs=(doc,))
        for lot in lots:
            target = next((l['key'] for l in version['lines'] if l['key'].startswith('F8949.') and l['key'].endswith('.'+lot)), 'F8949.MISSING.'+lot)
            add('investment.lot.'+doc+'.'+lot,'investments','Lot '+lot+' gain and basis',target,'Printed proceeds minus printed/supplemental basis plus wash adjustment; no missing basis default.',lambda c,d=doc,k=lot:lot_expected(c,d,k))
    for asset in packet['prior_years']['asset_records']:
        for jurisdiction in ('federal','california'):
            identifier = asset['asset_id']
            add('depreciation.opening.'+identifier+'.'+jurisdiction,'depreciation',identifier+' opening accumulated depreciation',None,'Sum prior-year per-asset depreciation and compare to current opening balance.',lambda c,a=identifier,j=jurisdiction:asset_roll(c,a,j),jurisdiction=jurisdiction)
    add('depreciation.rates','depreciation','Independent current-year depreciation rates',None,'No missing MACRS tables or conventions are manufactured.',unsupported('Independent per-asset current-year MACRS/AMT recomputation is unsupported without complete rate/convention tables; supplied engine amounts are not treated as independently verified.'))
    add('disposition.gain','depreciation','Rental sale gain roll-forward','F4797.25','Closing statement net consideration less independently rolled opening basis and supplied current-year depreciation.',sale,comparison='engine_consistency')
    add('disposition.recapture','depreciation','Ordinary versus unrecaptured section 1250','F4797.26g','Recapture treatment requires professional review; a carried engine zero is not proof.',unsupported('Independent recapture classification is not established by arithmetic alone; review depreciation method, property allocation and packet R-UNRECAPTURED-1250.'))
    def unrecaptured(c):
        depreciation = sum(prior_accum(c,a,'federal') + c.number('asset:'+a,('federal','depreciation_2025')) for a in ('AUS-BLDG','AUS-FLOOR'))
        return c.step('Packet R-UNRECAPTURED-1250: lesser of straight-line depreciation and reported gain; conditional on current engine depreciation',min(depreciation,c.line('F4797.25')))
    add('disposition.unrecaptured','depreciation','Unrecaptured 1250 depreciation consistency','SchD.19','Apply the supplied lesser-of rule to the documented depreciation bridge and reported gain.',unrecaptured,comparison='engine_consistency')
    add('rental.rent_a','rentals','Sacramento rental gross rents','SchE.3A','Compare owner-statement collected rent with Schedule E.',lambda c:c.amount('D46',r'Rent collected '+AMOUNT,'Sacramento rent collected'))
    add('rental.rent_b','rentals','Austin rental gross rents','SchE.3B','Multiply printed monthly rent by printed months rented.',lambda c:c.step('Printed monthly rent × nine documented rental months',c.amount('D50',r'Rent received January-September 2025: '+AMOUNT,'Austin monthly rent')*c.amount('D50',r'Rent received January-September 2025: [\d,]+\.\d+ x '+AMOUNT+r' =','Rental months')))
    add('rental.hvac','rentals','HVAC repair versus improvement','SchE.14A','Distinguish invoice facts from capitalization judgment.',unsupported('D47 describes replacement of the whole HVAC system. Capitalization requires a documented judgment; what_if.hvac_improvement is an engine alternative, not independent proof.'))
    add('california.wages','california','California wage sourcing conflict','SchCA540NR.1.E','Compare W-2 state wages with the residence-period paystub and relocation evidence.',ca_wages,jurisdiction='california',judgment=True)
    def ca_depreciation(c):
        assets=[a for a in c.version['assets'] if a['asset_id'].startswith('STU-')]
        if not assets:raise Unsupported('Studio asset inventory is absent.')
        return c.step('Current engine federal studio depreciation less current engine California studio depreciation; rate correctness not independently verified',sum(c.number('asset:'+a['asset_id'],('federal','depreciation_2025'))-c.number('asset:'+a['asset_id'],('california','depreciation_2025')) for a in assets))
    add('california.depreciation','california','Federal versus California business depreciation','SchCA540NR.12.C','Reconcile the asset-by-asset federal/California difference to Schedule CA.',ca_depreciation,jurisdiction='california',comparison='engine_consistency')
    add('california.amt','california','California AMT not computed','F540NR.61','Do not treat an engine placeholder zero as a verified tax.',unsupported('California AMT is explicitly not computed by the packet; no independent tax result is available.'),jurisdiction='california')
    add('california.capital_sourcing','california','California investment sourcing','SchCA540NR.7.E','Lot timing, basis corrections and residency interact.',unsupported('A complete corrected state-source gain requires resolved supplemental/crypto basis and residency allocations; no aggregate gain proration is assumed.'),jurisdiction='california')
    add('deductions.mortgage','itemized','Duplicate payoff mortgage interest','SchA.8a','Distinct Forms 1098 plus purchase points; payoff interest already included.',mortgage)
    add('deductions.property_tax','itemized','Seller property-tax credit','SchA.5b','Compare cash levy with seller allocation from the closing statement.',property_tax,judgment=True)
    add('deductions.salt_limit','itemized','SALT cap using reported MAGI','SchA.5e','Apply supplied cap, phaseout and floor; explicitly conditional on reported MAGI and SALT inputs.',salt_limit,comparison='engine_consistency')
    add('deductions.vehicle_gift','itemized','Vehicle gift value versus acknowledgment','F8283.A1.vehicle','Compare claimed value to acknowledgment gross proceeds; deductibility and exceptions require CPA judgment.',lambda c:c.amount('D66',r'4c gross proceeds from sale '+AMOUNT,'Vehicle acknowledgment proceeds'),judgment=True)
    add('deductions.cash_gift','itemized','Ambiguous cash donation acknowledgment','SchA.11','Conflicting/ambiguous receipt and subsequent client statement require substantiation.',unsupported('D64 has an ambiguous first digit and missing goods/services language. msg-08 is a later client assertion, not the referenced bank statement; no verified deduction is inferred.'))
    add('payments.federal_estimates','payments','Federal estimated payments','F1040.26','Use attributable IRS postings, not an uncorroborated organizer amount.',federal_estimates)
    add('payments.ca_estimates','payments','California payment tax-year designation','F540NR.72','Use FTB records designated tax year 2025.',state_estimates,jurisdiction='california')
    add('payments.federal_withholding','payments','Federal W-2 withholding','F1040.25a','Sum distinct printed W-2 box 2.',lambda c:withholding(c,'2'))
    add('payments.ca_withholding','payments','California W-2 withholding','F540NR.71','Sum distinct printed W-2 box 17.',lambda c:withholding(c,'17'),jurisdiction='california')
    for name,target in [('capital_loss_short','SchD.6'),('capital_loss_long','SchD.14')]:
        add('carryover.'+name,'carryovers',name+' beginning utilization',target,'Prior-year loss carryover enters Schedule D as a negative amount.',lambda c,k=name:-c.number('py:/carryovers_into_2025/'+k))
    add('carryover.outgoing','carryovers','Corrected outgoing carryovers',None,'Do not roll forward an uncorrected engine result as a verified balance.',unsupported('Full corrected carryover utilization depends on reconciled gains, losses and limitations. The engine carryovers_out remain available as reported, not independently proved.'))
    add('k1.scorp_income','pass_throughs','S corporation income','SchE.28A','Printed K-1 box 1 compared to return.',lambda c:c.amount('D39',r'Box 1 ordinary business income '+AMOUNT,'S corporation K-1 income'))
    add('k1.partnership_income','pass_throughs','Partnership rental income','SchE.28B','Printed K-1 box 2 compared to return.',lambda c:c.amount('D37',r'Box 2 net rental real estate income '+AMOUNT,'Partnership K-1 rental income'))
    add('k1.stock_basis','pass_throughs','S corporation beginning stock basis','F7203.1','Roll forward known basis years without filling undocumented adjustments.',basis,judgment=True)
    add('k1.outside_basis','pass_throughs','Partnership outside basis',None,'A capital account is not a substitute for outside basis.',unsupported('Prior-year outside basis is explicitly missing; capital account figures do not establish tax basis.'))
    add('rental.passive_loss','rentals','Current plus prior passive rental losses','SchE.26','Reconcile the reported rental-loss bridge; allowance eligibility is not independently recomputed.',passive,comparison='engine_consistency')
    return r


def _run_reconciliations(version='v3', packet=None):
    packet = packet if packet is not None else load_packet()
    baseline = next((v for v in packet['return_versions'] if v['version']==version),None)
    if baseline is None:
        return None
    results = []
    for rule in rules_for(packet,baseline):
        result = execute(rule,packet,baseline)
        results.append(result)
    # Firm standards are specifically prior-year variance standards, not a blanket tax tolerance.
    standard = packet['firm']['starter_standards']['variance_review']
    prior = packet['prior_years']['return_2024']['lines']
    for line in baseline['lines']:
        key = line['key']
        if key not in prior or not isinstance(line['value'],(int,float)) or isinstance(line['value'],bool):
            continue
        before,now = decimal(prior[key]),decimal(line['value'])
        difference = now-before
        percent = abs(difference/before)*100 if before else None
        over = percent is not None and percent>decimal(standard['flag_if_change_over_percent']) and abs(difference)>decimal(standard['and_over_amount'])
        rule = Rule('variance.'+key,'prior_year','Prior-year variance: '+key,key,'Firm prior-year variance thresholds: both percent and amount must be exceeded.',lambda c,b=before:c.number('py:/return_2024/lines/'+key),jurisdiction=line['jurisdiction'])
        result = execute(rule,packet,baseline)
        result.update(conclusion='material_discrepancy' if over else 'not_flagged_by_firm_variance_standard',
                      materiality={'scope':'prior_year_variance_only',**standard}, percent_change=display_percent(percent))
        if percent is None and difference:
            result.update(conclusion='judgment_required',reason='Prior year is zero; percentage change is undefined. No percentage threshold is invented.')
        results.append(result)
    return {'version':version,'checks':results,'total':len(results),'standards':standard,
            'scope':'Reconciles the selected engine baseline against the supplied packet, including later evidence. Does not rerun tax or apply adjustments to source values.'}


def display_percent(value):
    return format(value,'f') if value is not None else None


@lru_cache(maxsize=3)
def _cached_reconciliations(version):
    return _run_reconciliations(version,load_packet())


def run_reconciliations(version='v3',packet=None):
    if packet is not None:
        return _run_reconciliations(version,packet)
    from copy import deepcopy
    from app.services.firm_policy import current
    policy=current()
    if policy and policy['variance_review']!=load_packet()['firm']['starter_standards']['variance_review']:
        source=deepcopy(load_packet())
        source['firm']['starter_standards']['variance_review']=policy['variance_review']
        return _run_reconciliations(version,source)
    return deepcopy(_cached_reconciliations(version))
