from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json, math, statistics

class Trader:
    _AMETHYSTS = "AMETHYSTS"
    _STARFRUIT = "STARFRUIT"

    _POSITION_LIMITS = {
        _AMETHYSTS: 20,
        _STARFRUIT: 20
    }

    def run(self, state: TradingState):
        # Only method required. It takes all buy and sell orders for all symbols as an input, and outputs a list of orders to be sent
        print(f"traderData={state.traderData}")
        print(f"observations={str(state.observations)}")
        print(f"positions={str(state.position)}")
        if not state.traderData:
            state.traderData = json.dumps({self._AMETHYSTS: []})

        for key in self._POSITION_LIMITS.keys():
            if key not in state.position:
                state.position[key] = 0
        
        result = {}
        for product, incoming_orders in state.order_depths.items():
            if product == self._AMETHYSTS:
                print(f"product={product}, buy_orders={incoming_orders.buy_orders}")
                print(f"product={product}, sell_orders={incoming_orders.sell_orders}")
                orders, newTraderData = self.runAmethysts(state)
                result[product] = orders

            if product == self._STARFRUIT:
                # TODO: Complete me
                continue
            
        conversions = 1
        return result, conversions, json.dumps(newTraderData)

    def runAmethysts(self, state: TradingState) -> List[Order]:
        MIN_WINDOW, MAX_WINDOW = 3, 5
        product = self._AMETHYSTS
        order_depth = state.order_depths[product]
        orders: List[Order] = []

        limit = self._POSITION_LIMITS[product]
        position = state.position[product]

        # yield a dictionary of {<product>: [past N prices]}
        traderData: Dict[str, List[int]] = json.loads(state.traderData)
        
        acceptable_price = 10000 if len(traderData[product]) < MIN_WINDOW else statistics.mean(traderData[product])
        print(f"product={product}, acceptable_price={acceptable_price}")

        total_price_x_qty = 0
        total_qty = 0

        for sell_price, sell_qty in sorted(order_depth.sell_orders.items(), key=lambda x: x[0]):
            total_price_x_qty += sell_price * abs(sell_qty)
            total_qty += abs(sell_qty)

            if sell_price < acceptable_price:
                # max out position?
                # sell_qty is negative
                buy_qty = -sell_qty
                new_position = min(limit, max(-limit, position+buy_qty))
                exec_qty = new_position - position
                if exec_qty <= 0:
                    break

                # sell until nothing left?
                orders.append(Order(product, sell_price, exec_qty))        

                # Update position
                state.position[product] = new_position

                print(f"product={product}, order buy={orders[-1]}, position={state.position[product]}")

        for buy_price, buy_qty in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True):
            total_price_x_qty += buy_price * buy_qty 
            total_qty += buy_qty 

            if buy_price > acceptable_price:
                # max out position? 
                # buy_qty is positive
                sell_qty = -buy_qty
                new_position = min(limit, max(-limit, position+sell_qty))
                exec_qty = new_position - position
                if exec_qty >= 0:
                    break

                # sell until nothing left?
                orders.append(Order(product, buy_price, exec_qty))        

                # Update position
                state.position[product] = new_position

                print(f"product={product}, order sell={orders[-1]}, position={state.position[product]}")

        # calculate the new VWAP
        vwap = round(total_price_x_qty/max(1, total_qty))
        traderData[product].append(vwap)
        if len(traderData[product]) > MAX_WINDOW:
            traderData[product].pop(0)

        return orders, traderData
