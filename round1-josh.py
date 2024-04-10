from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List

class Trader:
    POSITION_LIMITS = {
        "AMETHYSTS" : 20,
        "STARFRUIT": 20
    }

    positions = {
        "AMETHYSTS": 0,
        "STARFRUIT": 0
    }

    def run(self, state: TradingState):
        # Only method required. It takes all buy and sell orders for all symbols as an input, and outputs a list of orders to be sent
        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))
        result = {}
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            if product == "AMETHYSTS":
                acceptable_price = 10000  # Participant should calculate this value
                spread = 0
            
            elif product == "STARFRUIT":
                acceptable_price = 5030 + (state.timestamp * 0.00025)
                spread = 0

            if len(order_depth.sell_orders) != 0:
                ask_fp = acceptable_price - spread
                best_ask = min(order_depth.sell_orders.keys())
                best_ask_vol = order_depth.sell_orders[best_ask]
                
                if best_ask <= ask_fp:
                    if self.positions[product] == self.POSITION_LIMITS[product]:
                        break

                    if self.positions[product] - best_ask_vol <= self.POSITION_LIMITS[product]:
                        print("BUY", str(-best_ask_vol) + "x", best_ask)
                        orders.append(Order(product, best_ask, -best_ask_vol))
                        self.positions[product] += -best_ask_vol
                    else:
                        max_vol = self.POSITION_LIMITS[product] - self.positions[product]
                        print("BUY", str(-max_vol) + "x", best_ask)
                        orders.append(Order(product, best_ask, -max_vol))
                        self.positions[product] += max_vol
    
            if len(order_depth.buy_orders) != 0:
                bid_fp = acceptable_price + spread

                best_bid = max(order_depth.buy_orders.keys())
                best_bid_vol = order_depth.buy_orders[best_bid]

                if best_bid >= bid_fp:
                    if self.positions[product] == -self.POSITION_LIMITS[product]:
                        break

                    if self.positions[product] - best_bid_vol >= -self.POSITION_LIMITS[product]:
                        print("SELL", str(best_bid_vol) + "x", best_bid)
                        orders.append(Order(product, best_bid, -best_bid_vol))
                        self.positions[product] += -best_bid_vol
                    else:
                        max_vol = self.positions[product] + self.POSITION_LIMITS[product]
                        print("SELL", str(max_vol) + "x", best_bid)
                        orders.append(Order(product, best_bid, -max_vol))
                        self.positions[product] += -max_vol

            result[product] = orders
    
        traderData = "SAMPLE" # String value holding Trader state data required. It will be delivered as TradingState.traderData on next execution.
        
        conversions = 1
        return result, conversions, traderData