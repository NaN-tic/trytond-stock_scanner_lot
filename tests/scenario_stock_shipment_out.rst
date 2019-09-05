
Stock Shipment Out Scenario
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
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock_scanner_lot Module::

    >>> Module = Model.get('ir.module')
    >>> modules = Module.find([('name', '=', 'stock_scanner_lot')])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> party = company.party

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)
    >>> config.user = 1

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

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

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
    >>> template.salable = True
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Configure stock::

    >>> StockConfig = Model.get('stock.configuration')
    >>> stock_config = StockConfig(1)
    >>> stock_config.scanner_on_shipment_out = True
    >>> stock_config.scanner_fill_quantity = True
    >>> stock_config.save()

Get stock locations::


    >>> Location = Model.get('stock.location')
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create a sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 10
    >>> sale.save()
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')


There is a shipment waiting::

    >>> shipment_out, = sale.shipments
    >>> len(shipment_out.outgoing_moves)
    1
    >>> len(shipment_out.inventory_moves)
    1
    >>> len(shipment_out.pending_moves)
    1
    >>> move, = shipment_out.pending_moves
    >>> move.pending_quantity
    10.0


Create 3 lots::

    >>> Lot = Model.get('stock.lot')
    >>> lots = []
    >>> for i in range(1,4):
    ...     lot = Lot(number='%05i' % i, product=product)
    ...     lot.save()
    ...     lots.append(lot)
    >>> lot1, lot2, lot3 = lots


Scan products and assign it::

    >>> len(shipment_out.pending_moves)
    1
    >>> shipment_out.scanned_product = product
    >>> shipment_out.scanned_quantity = 1.0
    >>> shipment_out.scanned_lot = lot1
    >>> shipment_out.click('scan')
    >>> move, = shipment_out.pending_moves
    >>> move.scanned_quantity == 1.0
    True
    >>> move.pending_quantity == 9.0
    True
    >>> move.lot == lot1
    True
    >>> shipment_out.scanned_product == None
    True
    >>> shipment_out.scanned_quantity == None
    True
    >>> shipment_out.scanned_lot == None
    True
    >>> shipment_out.scanned_product = product
    >>> shipment_out.scanned_quantity = 5.0
    >>> shipment_out.scanned_lot = lot2
    >>> shipment_out.click('scan')
    >>> len(shipment_out.pending_moves)
    1
    >>> len(shipment_out.inventory_moves)
    2
    >>> shipment_out.scanned_product = product
    >>> shipment_out.scanned_quantity = 2.0
    >>> shipment_out.scanned_lot = lot3
    >>> shipment_out.click('scan')
    >>> len(shipment_out.pending_moves)
    1
    >>> len(shipment_out.inventory_moves)
    3
    >>> shipment_out.scanned_product = product
    >>> shipment_out.scanned_quantity = 1.0
    >>> shipment_out.click('scan')
    >>> len(shipment_out.pending_moves)
    1
    >>> len(shipment_out.inventory_moves)
    4
    >>> shipment_out.scanned_product = product
    >>> shipment_out.scanned_quantity = 1.0
    >>> shipment_out.scanned_lot = lot3
    >>> shipment_out.click('scan')
    >>> len(shipment_out.pending_moves)
    0
    >>> len(shipment_out.inventory_moves)
    4
    >>> sorted([m.lot for m in shipment_out.inventory_moves]) == [None, lot1, lot2, lot3]
    True
