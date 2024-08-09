import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install Stock Scanner Lot Module
        config = activate_modules('stock_scanner_lot')

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        config._context = User.get_preferences(True, config.context)

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create customer
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        # Create category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name='Category')
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        product = Product()
        template = ProductTemplate()
        template.name = 'Product'
        template.account_category = account_category
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = Decimal('20')
        template.salable = True
        template.save()
        product.template = template
        product.save()

        # Configure stock
        StockConfig = Model.get('stock.configuration')
        stock_config = StockConfig(1)
        stock_config.scanner_on_shipment_out = True
        stock_config.scanner_fill_quantity = True
        stock_config.save()

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create a sale
        Sale = Model.get('sale.sale')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        sale.invoice_method = 'order'
        sale_line = sale.lines.new()
        sale_line.product = product
        sale_line.quantity = 10
        sale.save()
        sale.click('quote')
        sale.click('confirm')
        sale.click('process')

        # There is a shipment waiting
        shipment_out, = sale.shipments
        self.assertEqual(len(shipment_out.outgoing_moves), 1)
        self.assertEqual(len(shipment_out.inventory_moves), 1)
        self.assertEqual(len(shipment_out.pending_moves), 1)
        move, = shipment_out.pending_moves
        self.assertEqual(move.pending_quantity, 10.0)

        # Create 3 lots
        Lot = Model.get('stock.lot')
        lots = []
        for i in range(1, 4):
            lot = Lot(number='%05i' % i, product=product)
            lot.save()
            lots.append(lot)
        lot1, lot2, lot3 = lots

        # Scan products and assign it
        self.assertEqual(len(shipment_out.pending_moves), 1)
        shipment_out.scanned_product = product
        shipment_out.scanned_quantity = 1.0
        shipment_out.scanned_lot = lot1
        shipment_out.click('scan')
        move, = shipment_out.pending_moves
        self.assertEqual(move.scanned_quantity, 1.0)
        self.assertEqual(move.pending_quantity, 9.0)
        self.assertEqual(move.lot, lot1)
        self.assertEqual(shipment_out.scanned_product, None)
        self.assertEqual(shipment_out.scanned_quantity, None)
        self.assertEqual(shipment_out.scanned_lot, None)

        shipment_out.scanned_product = product
        shipment_out.scanned_quantity = 5.0
        shipment_out.scanned_lot = lot2
        shipment_out.click('scan')
        self.assertEqual(len(shipment_out.pending_moves), 1)
        self.assertEqual(len(shipment_out.inventory_moves), 2)

        shipment_out.scanned_product = product
        shipment_out.scanned_quantity = 2.0
        shipment_out.scanned_lot = lot3
        shipment_out.click('scan')
        self.assertEqual(len(shipment_out.pending_moves), 1)
        self.assertEqual(len(shipment_out.inventory_moves), 3)

        shipment_out.scanned_product = product
        shipment_out.scanned_quantity = 1.0
        shipment_out.click('scan')
        self.assertEqual(len(shipment_out.pending_moves), 1)
        self.assertEqual(len(shipment_out.inventory_moves), 3)

        shipment_out.scanned_product = product
        shipment_out.scanned_quantity = 1.0
        shipment_out.scanned_lot = lot3
        shipment_out.click('scan')
        self.assertEqual(len(shipment_out.pending_moves), 0)
        self.assertEqual(len(shipment_out.inventory_moves), 3)
        self.assertEqual(
            sorted([str(m.lot) for m in shipment_out.inventory_moves]),
                   [str(lot1), str(lot2), str(lot3)])
