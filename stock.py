# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSQL, fields
from trytond.pyson import Bool, Eval, If
from trytond.pool import Pool, PoolMeta
from trytond.modules.stock_scanner.stock import MIXIN_STATES
from datetime import datetime
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)


__all__ = ['Configuration', 'ConfigurationScannerLotCreation',
    'ShipmentIn', 'ShipmentOut', 'ShipmentInReturn', 'ShipmentOutReturn']

LOT_CREATION_MODES = [
            (None, ''),
            ('search-create', 'Search reference & create'),
            ('always', 'Always')
            ]


class Configuration(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    scanner_lot_creation = fields.MultiValue(fields.Selection(
            LOT_CREATION_MODES, 'Lot Creation', required=False,
            help='If set to "Search reference & create" the system will search '
            'the reference introduced in the lot and will create one if it\'s not '
            'found. If set to "Always" it will create a lot even if one with the '
            'same number exists. All this always takes place if a scanned lot is '
            'not selected.'))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'scanner_lot_creation':
            return pool.get('stock.configuration.scanner_lot_creation')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_scanner_lot_creation(cls, **pattern):
        model = cls.multivalue_model('scanner_lot_creation')
        return model.default_scanner_lot_creation()


class ConfigurationScannerLotCreation(ModelSQL, CompanyValueMixin):
    'Stock Configuration Scanner Lot Creation'
    __name__ = 'stock.configuration.scanner_lot_creation'

    scanner_lot_creation = fields.Selection(
        LOT_CREATION_MODES, 'Lot Creation')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationScannerLotCreation, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('scanner_lot_creation')
        value_names.append('scanner_lot_creation')
        fields.append('company')
        migrate_property(
            'stock.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_scanner_lot_creation(cls):
        return None


class StockScanMixin(object):
    scanned_lot_number = fields.Char('Scanned Lot Number', states={
        'readonly': (Bool(Eval('scanned_lot', False))
                    | ~Eval('state', 'draft').in_(['waiting', 'draft'])),
        }, depends=['state', 'scanned_lot'],
        help="Lot number of the lot that will be scanned.")
    scanned_lot = fields.Many2One('stock.lot', 'Stock Lot', domain=[
            If(Bool(Eval('scanned_product')),
                ('product', '=', Eval('scanned_product')),
                ()),
            ],
        states=MIXIN_STATES, depends=['state', 'scanned_product'])

    def clear_scan_values(self):
        super(StockScanMixin, self).clear_scan_values()
        self.scanned_lot_number = None
        self.scanned_lot = None

    def get_processed_move(self):
        move = super(StockScanMixin, self).get_processed_move()
        move.lot = self.scanned_lot
        return move

    @fields.depends('scanned_lot')
    def on_change_scanned_lot(self):
        if self.scanned_lot:
            self.scanned_lot_number = self.scanned_lot.number

    @fields.depends('scanned_lot', 'scanned_lot_number', 'scanned_product')
    def on_change_scanned_lot_number(self):
        pool = Pool()
        Lot = pool.get('stock.lot')
        if not self.scanned_lot and self.scanned_lot_number:
            lots = Lot.search([
                ('number', '=', self.scanned_lot_number),
                ('product', '=', self.scanned_product)
                ], limit=1)
            if lots:
                self.scanned_lot, = lots

    def _adjust_pending_moves(self):
        """
        If there aren't matching moves, a new one is created, then the amount
        of one of the pending movements must be adjusted with the coincidence
        of the product and the amount pending.
        """
        for move in self.pending_moves:
            if (move.product == self.scanned_product
                    and (move.pending_quantity - self.scanned_quantity) >= 0):
                move.quantity -= self.scanned_quantity
                move.save()
                return move

    def _is_needed_to_create_lot(self):
        return False

    def get_matching_moves(self):
        """Get possible scanned move"""
        moves = super(StockScanMixin, self).get_matching_moves()
        match_moves = []
        w_lot_moves = []
        if self.scanned_lot_number:
            if self._is_needed_to_create_lot():
                return []
            for move in moves:
                if move.lot and self.scanned_lot == move.lot:
                    match_moves.append(move)
                elif not move.lot and not move.scanned_quantity:
                    w_lot_moves.append(move)

            if not match_moves:
                no_pending_moves = list(set(self.get_pick_moves()) -
                    set(self.pending_moves))
                for move in no_pending_moves:
                    if (move.product == self.scanned_product and
                            move.lot == self.scanned_lot):
                        match_moves.append(move)
                        break
            return match_moves or w_lot_moves

        return moves

    def process_moves(self, moves):
        is_not_pending_move = len(moves) == 1 and not moves[0].pending_quantity
        adjusted_move = None
        if (not moves and self.scanned_quantity) or is_not_pending_move:
            adjusted_move = self._adjust_pending_moves()
            if is_not_pending_move:
                moves[0].quantity += self.scanned_quantity
        move = super(StockScanMixin, self).process_moves(moves)
        if not move.origin and adjusted_move:
            move.origin = adjusted_move.origin
        if not move.lot:
            move.lot = self.scanned_lot
        if move._save_values:
            move.save()
        return move


class ShipmentIn(StockScanMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _is_needed_to_create_lot(self):

        pool = Pool()
        Config = pool.get('stock.configuration')

        if not self.scanned_product:
            return False

        config = Config(1)
        lot_creation_method = config.scanner_lot_creation
        lot_required = 'supplier' in {t.code for t in
            self.scanned_product.template.lot_required}
        return (lot_creation_method == 'always' or
            (not self.scanned_lot and (lot_required
                or (self.scanned_lot_number and lot_creation_method ==
                    'search-create'))))

    def _create_lot(self):
        pool = Pool()
        Lot = pool.get('stock.lot')
        default_lot_number = datetime.today().strftime('%Y-%m-%d')
        lot_number = (self.scanned_lot_number or
            default_lot_number)
        lot = Lot()
        lot.product = self.scanned_product
        lot.number = lot_number
        return lot

    def process_moves(self, moves):
        if not self.scanned_lot:
            if self._is_needed_to_create_lot():
                lot = self._create_lot()
                self.scanned_lot = lot
                self.save()
                moves = []
        return super(ShipmentIn, self).process_moves(moves)


class ShipmentInReturn(ShipmentIn, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentOut(StockScanMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentOutReturn(ShipmentOut, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'
