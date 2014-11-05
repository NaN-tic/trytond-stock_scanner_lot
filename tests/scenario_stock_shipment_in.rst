===========================
Stock Shipment In Scenario
===========================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([('name', '=', 'stock_scanner_lot')])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='OPENLABS')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

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
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='supplier')
    >>> supplier.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> category = ProductCategory(name='Category')
    >>> category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.category = category
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('8')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.purchasable = True
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Configure stock::

    >>> StockConfig = Model.get('stock.configuration')
    >>> lot_seq = Sequence(name=str(today.year), code='stock.lot',
    ...     company=company)
    >>> lot_seq.save()
    >>> stock_config = StockConfig(1)
    >>> stock_config.scanner_lot_creation = 'search-create'
    >>> stock_config.lot_sequence = lot_seq
    >>> stock_config.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create a purchase::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 10
    >>> purchase.save()
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> move, = purchase.moves

Create a shipment to receive the products::

    >>> Move = Model.get('stock.move')
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment_in = ShipmentIn()
    >>> shipment_in.supplier = supplier
    >>> for move in purchase.moves:
    ...     incoming_move = Move(id=move.id)
    ...     shipment_in.incoming_moves.append(incoming_move)
    >>> shipment_in.save()

Scan products and assign it::

    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 1.0
    >>> shipment_in.scanned_lot_ref = '1'
    >>> shipment_in.click('scan')
    >>> move, = shipment_in.pending_moves
    >>> move.received_quantity == 1.0
    True
    >>> move.pending_quantity == 9.0
    True
    >>> move.lot.number == '1'
    True
    >>> shipment_in.scanned_product == None
    True
    >>> shipment_in.scanned_quantity == 0.0
    True
    >>> shipment_in.scanned_lot_ref == None
    True
    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 1.0
    >>> shipment_in.scanned_lot_ref = '1'
    >>> shipment_in.click('scan')
    >>> move, = shipment_in.pending_moves
    >>> move.received_quantity == 2.0
    True
    >>> move.pending_quantity == 8.0
    True
    >>> move.lot.number == '1'
    True
    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 1.0
    >>> shipment_in.scanned_lot_ref = '2'
    >>> shipment_in.click('scan')
    >>> len(shipment_in.pending_moves)
    1
    >>> len(shipment_in.incoming_moves)
    2

Set the state as Done::

    >>> Lot = Model.get('stock.lot')
    >>> ShipmentIn.receive([shipment_in.id], config.context)
    >>> ShipmentIn.done([shipment_in.id], config.context)
    >>> shipment_in.reload()
    >>> len(shipment_in.incoming_moves)
    2
    >>> len(shipment_in.inventory_moves)
    2
    >>> len(shipment_in.pending_moves)
    0
    >>> sum([m.quantity for m in shipment_in.inventory_moves]) == \
    ...     sum([m.quantity for m in shipment_in.incoming_moves])
    True
    >>> [x.number for x in Lot.find([])]
    [u'1', u'2']




