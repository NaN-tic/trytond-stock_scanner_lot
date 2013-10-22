# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.modules.stock_scanner.stock import MIXIN_STATES


__all__ = ['Configuration', 'ShipmentIn', 'ShipmentInReturn', 'ShipmentOut',
    'ShipmentOutReturn']

__metaclass__ = PoolMeta


class Configuration:
    __name__ = 'stock.configuration'

    scanner_lot_creation = fields.Property(fields.Selection([
            ('search-create', 'Search reference & create'),
            ('always', 'Always')
            ], 'Lot Creation', required=False,
        help='If set to "Search reference & create" the system will search the'
        ' reference introduced in the lot and will create one if it''s not '
        'found. If set to "Always" it will create a lot even if one with the'
        'same number exists.'))


class StockScanMixin(object):

    scanned_lot_ref = fields.Char('Supplier Lot Ref.', depends=['state'],
        states=MIXIN_STATES, help="Supplier's lot reference.")
    scanned_lot = fields.Many2One('stock.lot', 'Stock Lot',
        states=MIXIN_STATES, depends=['state', 'scanned_product'],
        domain=[('product', '=', Eval('scanned_product'))],
        )

    @classmethod
    def clear_scan_values(cls, shipments):
        cls.write(shipments, {
            'scanned_lot_ref': None,
            'scanned_lot': None,
        })
        super(StockScanMixin, cls).clear_scan_values(shipments)

    @classmethod
    def process_moves(cls, moves):
        cls.process_in_moves(moves)
        cls.process_out_moves(moves)

    @classmethod
    def process_in_moves(cls, moves):
        pass

    @classmethod
    def process_out_moves(cls, moves):
        pass


class ShipmentIn(StockScanMixin):
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.in'

    @classmethod
    def process_in_moves(cls, moves):
        pool = Pool()
        Config = pool.get('stock.configuration')
        Move = pool.get('stock.move')
        Lot = pool.get('stock.lot')

        config = Config(1)
        lot_creation = config.scanner_lot_creation

        for move in moves:
            qty = min(move.shipment.scanned_quantity, move.pending_quantity)
            if qty == 0:
                continue

            lot = None
            lot_ref = move.shipment.scanned_lot_ref
            input_lot = lot_ref and len(lot_ref) > 0

            lot_required = move.product.lot_is_required(move.from_location,
                    move.to_location)

            if lot_creation == 'search-create' and input_lot:
                lots = Lot.search([('supplier_ref', '=', lot_ref)])
                if lots:
                    lot = lots[0]
                else:
                    lot_required = True

            if lot_required and not lot:
                if move.lot and not input_lot:
                    lot = move.lot
                else:
                    lot = Lot(product=move.shipment.scanned_product)
                    if input_lot:
                        lot.supplier_ref = lot_ref
                    lot.save()

            if move.lot and move.lot != lot:
                pending = move.pending_quantity
                move.quantity = move.received_quantity
                move.save()
                move, = Move.copy([move], {
                    'quantity': pending,
                    'received_quantity': 0,
                    'state': move.state,
                    'lot': None,
                })
            move.received_quantity = (move.received_quantity or 0.0) + qty
            move.lot = lot

            if move.shipment.scanned_unit_price:
                move.unit_price = move.shipment.scanned_unit_price
            move.save()

    def get_matching_moves(self):
        """Get possible scanned move"""
        moves = super(ShipmentIn, self).get_matching_moves()
        new_moves = []
        for move in moves:
            if move.lot and move.lot.number == self.scanned_lot_ref:
                new_moves.insert(0, move)
                continue
            new_moves.append(move)
        return new_moves


class ShipmentInReturn(ShipmentIn):
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.in.return'


class ShipmentOut(StockScanMixin):
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.out'

    @classmethod
    def process_out_moves(cls, moves):
        pool = Pool()
        Move = pool.get('stock.move')
        for move in moves:
            qty = min(move.shipment.scanned_quantity, move.pending_quantity)
            if qty == 0:
                continue

            lot = move.shipment.scanned_lot or move.lot or None
            if move.lot and move.lot != lot:
                pending = move.pending_quantity
                move.quantity = move.received_quantity
                move.save()
                move, = Move.copy([move], {
                    'quantity': pending,
                    'received_quantity': 0,
                    'state': move.state,
                    'lot': None,
                })

            move.received_quantity = (move.received_quantity or 0.0) + qty
            move.lot = lot
            move.save()

    def get_matching_moves(self):
        """Get possible scanned move"""
        moves = super(ShipmentOut, self).get_matching_moves()
        new_moves = []
        for move in moves:
            if self.scanned_lot and move.lot:
                if self.scanned_lot == move.lot:
                    new_moves.insert(0, move)
                    continue
            new_moves.append(move)
        return new_moves


class ShipmentOutReturn(ShipmentOut):
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.out.return'
