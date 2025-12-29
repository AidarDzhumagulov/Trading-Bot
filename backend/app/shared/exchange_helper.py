class TradingUtils:
    """
    Класс помощник для округления получения данных  и тд
    """

    def __init__(self, exchange):
        self.exchange = exchange
        self._markets_loaded = False

    async def ensure_markets_loaded(self):
        if not self._markets_loaded:
            await self.exchange.load_markets()
            self._markets_loaded = True

    async def get_market(self, symbol):
        await self.ensure_markets_loaded()
        return self.exchange.market(symbol)

    async def round_amount(self, symbol, amount):
        await self.ensure_markets_loaded()
        return float(self.exchange.amount_to_precision(symbol, amount))

    async def round_price(self, symbol, price):
        await self.ensure_markets_loaded()
        return float(self.exchange.price_to_precision(symbol, price))

    async def check_min_notional(self, symbol, amount, price):
        market = await self.get_market(symbol)
        min_cost = market.get('limits', {}).get('cost', {}).get('min', 0)
        if min_cost > 0:
            cost = float(amount) * float(price)
            return cost >= min_cost
        return True

    async def get_amount_precision(self, symbol):
        market = await self.get_market(symbol)
        precision = market.get('precision', {}).get('amount', 8)
        if isinstance(precision, int):
            return precision
        return 8

    async def get_price_precision(self, symbol):
        market = await self.get_market(symbol)
        precision = market.get('precision', {}).get('price', 2)
        if isinstance(precision, int):
            return precision
        return 2
