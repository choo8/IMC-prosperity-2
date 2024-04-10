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
        # Update positions
        for product, position in state.position.items():
            self.positions[product] = position

        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            if product == "AMETHYSTS":
                acceptable_price = 10000  # Eyeball graph

                best_market_ask = min(order_depth.sell_orders.keys())
                best_market_bid = max(order_depth.buy_orders.keys())

                cur_position = self.positions[product]

                # Construct buy orders
                for ask, vol in order_depth.sell_orders.items():
                    # Check if asking price is below 
                    if ((ask < acceptable_price) or ((self.positions[product] < 0) and (ask == acceptable_price))) and cur_position < self.POSITION_LIMITS[product]:
                        order_vol = min(-vol, self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("BUY", str(order_vol) + "x", ask)
                        orders.append(Order(product, ask, order_vol))

                market_price = (best_market_ask + best_market_bid) / 2
                own_price = acceptable_price

                # Derived from actual AMETHYSTS prices from previous iteration
                undercut_market_ask = best_market_ask - 1
                undercut_market_bid = best_market_bid + 1

                # Spread = 1
                own_ask = max(undercut_market_ask, acceptable_price + 1)
                own_bid = min(undercut_market_bid, acceptable_price - 1)

                # If position limits are not yet hit, try to buy more
                if cur_position < self.POSITION_LIMITS[product]:
                    # Current position is short
                    if self.positions[product] < 0:
                        # We want to try to balance position, give less aggressive bid
                        ask = min(undercut_market_bid + 1, acceptable_price - 1)
                    # Current position is long, close to limit
                    elif self.positions[product] > 15:
                        # Close to limit, don't need that many more, can give more aggressive bid
                        ask = min(undercut_market_bid - 1, acceptable_price - 1)
                    # Current position is long, not close to limit
                    else:
                        ask = own_bid

                    order_vol = min(self.POSITION_LIMITS[product], self.POSITION_LIMITS[product] - cur_position)
                    cur_position += order_vol
                    print("BUY", str(order_vol) + "x", ask)
                    orders.append(Order(product, ask, order_vol))

                cur_position = self.positions[product]
        
                # Construct sell orders
                for bid, vol in order_depth.buy_orders.items():
                    if ((bid > acceptable_price) or ((self.positions[product] > 0) and (bid == acceptable_price))) and cur_position > -self.POSITION_LIMITS[product]:
                        order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("SELL", str(order_vol) + "x", bid)
                        orders.append(Order(product, bid, order_vol))
                
                if cur_position > -self.POSITION_LIMITS[product]:
                    if self.positions[product] < 0:
                        bid = max(undercut_market_ask - 1, acceptable_price + 1)
                    elif self.positions[product] < -15:
                        bid = max(undercut_market_ask + 1, acceptable_price + 1)
                    else:
                        bid = own_ask

                    order_vol = max(-self.POSITION_LIMITS[product], -self.POSITION_LIMITS[product] - cur_position)
                    cur_position += order_vol
                    print("SELL", str(order_vol) + "x", bid)
                    orders.append(Order(product, bid, order_vol))

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