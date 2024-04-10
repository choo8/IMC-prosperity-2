from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List


class Trader:
    _AMETHYSTS = "AMETHYSTS"
    _STARFRUIT = "STARFRUIT"

    _POSITION_LIMITS = {
        _AMETHYSTS: 20,
        _STARFRUIT: 20
    }

    def run(self, state: TradingState):
        # Only method required. It takes all buy and sell orders for all symbols as an input, and outputs a list of orders to be sent
        print(f"time={state.timestamp}, traderData={state.traderData}")
        print(f"time={state.timestamp}, observations={str(state.observations)}")
        print(f"time={state.timestamp}, positions={str(state.position)}")

        for key in self._POSITION_LIMITS.keys():
            if key not in state.position:
                state.position[key] = 0
        
        # TODO: Complete me
        result = {}
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            if product == self._AMETHYSTS:
                # TODO: Complete me
                print(f"time={state.timestamp}, product={product}, buy_orders={order_depth.buy_orders}")
                print(f"time={state.timestamp}, product={product}, sell_orders={order_depth.sell_orders}")

                # if above 10k, sell
                # if below 10k, buy
                acceptable_price = 10000
                for buy_price, buy_qty in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True):
                    if buy_price > acceptable_price:
                        # max out position? 
                        qty = max(-buy_qty, max(-self._POSITION_LIMITS[product], -self._POSITION_LIMITS[product]-state.position[product]))
                        if qty >= 0:
                            break

                        # sell until nothing left?
                        orders.append(Order(product, buy_price, qty))        
                        print(f"time={state.timestamp}, SELL: {orders[-1]}")

                        # Update position
                        state.position[product] -= qty

                for sell_price, sell_qty in sorted(order_depth.sell_orders.items(), key=lambda x: x[0]):
                    if sell_price < acceptable_price:
                        # max out position? 
                        qty = min(sell_qty, min(self._POSITION_LIMITS[product], self._POSITION_LIMITS[product]-state.position[product]))
                        if qty <= 0:
                            break

                        # sell until nothing left?
                        orders.append(Order(product, sell_price, qty))        
                        print(f"time={state.timestamp}, BUY: {orders[-1]}")

                        # Update position
                        state.position[product] += qty
                
                result[product] = orders

            if product == self._STARFRUIT:
                # TODO: Complete me
                continue
            

        traderData = str(state)
        conversions = 1
        return result, conversions, traderData
