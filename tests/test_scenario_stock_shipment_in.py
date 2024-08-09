import datetime
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

        # Create supplier
        Party = Model.get('party.party')
        supplier = Party(name='supplier')
        supplier.save()

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
        template.cost_price = Decimal('8')
        template.purchasable = True
        template.save()
        product.template = template
        product.save()

        # Configure stock
        StockConfig = Model.get('stock.configuration')
        stock_config = StockConfig(1)
        stock_config.scanner_on_shipment_in = True
        stock_config.scanner_lot_creation = 'search-create'
        stock_config.save()

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create a purchase
        Purchase = Model.get('purchase.purchase')
        purchase = Purchase()
        purchase.party = supplier
        purchase.payment_term = payment_term
        purchase_line = purchase.lines.new()
        purchase_line.product = product
        purchase_line.quantity = 10
        purchase.save()
        purchase.click('quote')
        purchase.click('confirm')
        purchase.click('process')
        move, = purchase.moves

        # Create a shipment to receive the products
        Move = Model.get('stock.move')
        ShipmentIn = Model.get('stock.shipment.in')
        shipment_in = ShipmentIn()
        shipment_in.supplier = supplier
        for move in purchase.moves:
            incoming_move = Move(id=move.id)
            shipment_in.incoming_moves.append(incoming_move)
        shipment_in.save()

        # Scan products and assign it
        shipment_in.scanned_product = product
        shipment_in.scanned_quantity = 1.0
        shipment_in.save()
        shipment_in.click('scan')
        move, = shipment_in.pending_moves
        self.assertEqual(move.scanned_quantity, 1.0)
        self.assertEqual(move.pending_quantity, 9.0)
        self.assertEqual(move.lot, None)
        self.assertEqual(shipment_in.scanned_product, None)
        self.assertEqual(shipment_in.scanned_quantity, None)
        self.assertEqual(shipment_in.scanned_lot_number, None)

        product.template.lot_required = ['supplier']
        product.template.save()
        shipment_in.scanned_product = product
        shipment_in.scanned_quantity = 1.0
        shipment_in.scanned_lot_number = '1'
        shipment_in.save()
        shipment_in.click('scan')
        self.assertEqual(len(shipment_in.pending_moves), 1)
        self.assertEqual(len(shipment_in.incoming_moves), 2)

        move = shipment_in.incoming_moves[1]
        self.assertEqual(move.scanned_quantity, 1.0)
        self.assertEqual(move.quantity, 1.0)
        self.assertEqual(move.pending_quantity, 0.0)
        self.assertEqual(move.lot.number, '1')

        shipment_in.scanned_product = product
        shipment_in.scanned_quantity = 1.0
        shipment_in.scanned_lot_number = '2'
        shipment_in.click('scan')
        self.assertEqual(len(shipment_in.pending_moves), 1)
        self.assertEqual(len(shipment_in.incoming_moves), 3)
        self.assertEqual(product.template.lot_required, ('supplier', ))

        shipment_in.scanned_product = product
        shipment_in.scanned_quantity = 3.0
        shipment_in.save()
        shipment_in.click('scan')
        self.assertEqual(len(shipment_in.pending_moves), 1)
        self.assertEqual(len(shipment_in.incoming_moves), 4)

        move = shipment_in.incoming_moves[2]
        self.assertEqual(move.scanned_quantity, 1.0)
        self.assertEqual(move.pending_quantity, 0.0)
        self.assertEqual(move.lot.number, '2')

        shipment_in.scanned_product = product
        shipment_in.scanned_quantity = 1.0
        shipment_in.scanned_lot_number = '2'
        shipment_in.click('scan')
        self.assertEqual(len(shipment_in.pending_moves), 1)
        self.assertEqual(len(shipment_in.incoming_moves), 4)

        move = shipment_in.incoming_moves[3]
        self.assertEqual(move.scanned_quantity, 3.0)
        self.assertEqual(move.pending_quantity, 0.0)

        stock_config.scanner_lot_creation = 'always'
        stock_config.save()
        shipment_in.scanned_product = product
        shipment_in.scanned_quantity = 3.0
        shipment_in.click('scan')
        self.assertEqual(len(shipment_in.pending_moves), 0)
        self.assertEqual(len(shipment_in.incoming_moves), 5)

        move = shipment_in.incoming_moves[3]
        self.assertEqual(move.lot.number,
                         datetime.date.today().strftime('%Y-%m-%d'))

        # Set the state as Done
        Lot = Model.get('stock.lot')
        product.template.lot_required = []
        product.template.save()
        ShipmentIn.receive([shipment_in.id], config.context)
        ShipmentIn.done([shipment_in.id], config.context)
        shipment_in.reload()
        self.assertEqual(len(shipment_in.incoming_moves), 5)
        self.assertEqual(len(shipment_in.inventory_moves), 5)
        self.assertEqual(len(shipment_in.pending_moves), 0)
        self.assertEqual(
            sum([m.quantity for m in shipment_in.inventory_moves]),
            sum([m.quantity for m in shipment_in.incoming_moves]))
        self.assertEqual([x.number for x in Lot.find([])], [
            '1', '2',
            datetime.date.today().strftime('%Y-%m-%d'),
            datetime.date.today().strftime('%Y-%m-%d')
        ])
