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
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.tests.tools import activate_modules
    >>> today = datetime.date.today()

Install Stock Scanner Lot Module::

    >>> config = activate_modules('stock_scanner_lot')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> party = company.party

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='supplier')
    >>> supplier.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name='Category')
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.account_category = account_category
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('8')
    >>> template.purchasable = True
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Configure stock::

    >>> StockConfig = Model.get('stock.configuration')
    >>> stock_config = StockConfig(1)
    >>> stock_config.scanner_on_shipment_in = True
    >>> stock_config.scanner_lot_creation = 'search-create'
    >>> stock_config.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create payment term::

    >>> payment_term = create_payment_term()
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
    >>> shipment_in.save()
    >>> shipment_in.click('scan')
    >>> move, = shipment_in.pending_moves
    >>> move.scanned_quantity == 1.0
    True
    >>> move.pending_quantity == 9.0
    True
    >>> move.lot == None
    True
    >>> shipment_in.scanned_product == None
    True
    >>> shipment_in.scanned_quantity == None
    True
    >>> shipment_in.scanned_lot_number == None
    True
    >>> product.template.lot_required = ['supplier']
    >>> product.template.save()
    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 1.0
    >>> shipment_in.scanned_lot_number = '1'
    >>> shipment_in.save()
    >>> shipment_in.click('scan')
    >>> len(shipment_in.pending_moves)
    1
    >>> len(shipment_in.incoming_moves)
    2
    >>> move = shipment_in.incoming_moves[0]
    >>> move.scanned_quantity == 1.0
    True
    >>> move.quantity == 1.0
    True
    >>> move.pending_quantity == 0.0
    True
    >>> move.lot.number == '1'
    True
    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 1.0
    >>> shipment_in.scanned_lot_number = '2'
    >>> shipment_in.click('scan')
    >>> len(shipment_in.pending_moves)
    1
    >>> len(shipment_in.incoming_moves)
    3
    >>> product.template.lot_required == ['supplier']
    True
    >>> product.template.save()
    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 3.0
    >>> shipment_in.save()
    >>> shipment_in.click('scan')
    >>> len(shipment_in.pending_moves)
    1
    >>> len(shipment_in.incoming_moves)
    3
    >>> move = shipment_in.incoming_moves[2]
    >>> move.scanned_quantity == 4.0
    True
    >>> move.pending_quantity == 4.0
    True
    >>> move.lot == None
    True
    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 1.0
    >>> shipment_in.scanned_lot_number = '2'
    >>> shipment_in.click('scan')
    >>> len(shipment_in.pending_moves)
    1
    >>> len(shipment_in.incoming_moves)
    3
    >>> move = shipment_in.incoming_moves[0]
    >>> move.scanned_quantity == 2.0
    True
    >>> move.pending_quantity == 0.0
    True
    >>> stock_config.scanner_lot_creation = 'always'
    >>> stock_config.save()
    >>> shipment_in.scanned_product = product
    >>> shipment_in.scanned_quantity = 3.0
    >>> shipment_in.click('scan')
    >>> len(shipment_in.pending_moves)
    0
    >>> len(shipment_in.incoming_moves)
    4
    >>> move = shipment_in.incoming_moves[0]
    >>> move.lot.number == today.strftime('%Y-%m-%d')
    True

Set the state as Done::

    >>> Lot = Model.get('stock.lot')
    >>> ShipmentIn.receive([shipment_in.id], config.context)
    >>> ShipmentIn.done([shipment_in.id], config.context)
    >>> shipment_in.reload()
    >>> len(shipment_in.incoming_moves)
    4
    >>> len(shipment_in.inventory_moves)
    4
    >>> len(shipment_in.pending_moves)
    0
    >>> sum([m.quantity for m in shipment_in.inventory_moves]) == \
    ...     sum([m.quantity for m in shipment_in.incoming_moves])
    True
    >>> [x.number for x in Lot.find([])] == [u'1', u'2', today.strftime('%Y-%m-%d')]
    True
