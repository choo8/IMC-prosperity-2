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

    # Linear regression parameters trained on data from days -2, -1 and 0
    starfruit_coef = [0.19276398, 0.22111366, 0.24350053, 0.34038018]
    starfruit_intercept = 11.302935408693884

    # Cache latest 4 midprice of best_ask and best_bid every iteration
    starfruit_cache = []

    def compute_starfruit_price(self):
        price = self.starfruit_intercept
        
        for idx, cached_price in enumerate(self.starfruit_cache):
            price += self.starfruit_coef[idx] * cached_price
        
        return int(round(price))

    def run(self, state: TradingState):
        # Update positions
        for product, position in state.position.items():
            self.positions[product] = position

        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            best_market_ask = min(order_depth.sell_orders.keys())
            best_market_bid = max(order_depth.buy_orders.keys())
            
            market_price = (best_market_ask + best_market_bid) / 2

            if product == "AMETHYSTS":
                acceptable_price = 10000  # Eyeball graph

                cur_position = self.positions[product]

                # Market make
                for ask, vol in order_depth.sell_orders.items():
                    # Check if asking price is below 
                    if ((ask < acceptable_price) or ((self.positions[product] < 0) and (ask == acceptable_price))) and cur_position < self.POSITION_LIMITS[product]:
                        order_vol = min(-vol, self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("BUY", product, str(order_vol) + "x", ask)
                        orders.append(Order(product, ask, order_vol))

                # Derived from actual AMETHYSTS prices from previous iteration
                undercut_market_ask = best_market_ask - 1
                undercut_market_bid = best_market_bid + 1

                # Spread = 1
                own_ask = max(undercut_market_ask, acceptable_price + 1)
                own_bid = min(undercut_market_bid, acceptable_price - 1)

                # Market take
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
                    print("BUY", product, str(order_vol) + "x", ask)
                    orders.append(Order(product, ask, order_vol))

                cur_position = self.positions[product]
        
                # Market make
                for bid, vol in order_depth.buy_orders.items():
                    if ((bid > acceptable_price) or ((self.positions[product] > 0) and (bid == acceptable_price))) and cur_position > -self.POSITION_LIMITS[product]:
                        order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("SELL", product, str(order_vol) + "x", bid)
                        orders.append(Order(product, bid, order_vol))
                
                # Market take
                if cur_position > -self.POSITION_LIMITS[product]:
                    if self.positions[product] < 0:
                        bid = max(undercut_market_ask - 1, acceptable_price + 1)
                    elif self.positions[product] < -15:
                        bid = max(undercut_market_ask + 1, acceptable_price + 1)
                    else:
                        bid = own_ask

                    order_vol = max(-self.POSITION_LIMITS[product], -self.POSITION_LIMITS[product] - cur_position)
                    cur_position += order_vol
                    print("SELL", product, str(order_vol) + "x", bid)
                    orders.append(Order(product, bid, order_vol))

            elif product == "STARFRUIT":
                # Pop oldest value from starfruit_cache if full
                if len(self.starfruit_cache) == 4:
                    self.starfruit_cache.pop(0)

                # Cache STARFRUIT prices
                self.starfruit_cache.append(market_price)
                # print(self.starfruit_cache)

                # Estimate price via linear regression
                if len(self.starfruit_cache) == 4:
                    acceptable_price = self.compute_starfruit_price()
                    # print(acceptable_price)
                    lower_bound = acceptable_price - 1
                    upper_bound = acceptable_price + 1
                else:
                    lower_bound = -int(1e9)
                    upper_bound = int(1e9)

                cur_position = self.positions[product]

                # Construct buy orders
                for ask, vol in order_depth.sell_orders.items():
                    if ((ask <= lower_bound) or ((self.positions[product] < 0) and ask == lower_bound + 1)) and cur_position < self.POSITION_LIMITS[product]:
                        order_vol = min(-vol, self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("BUY", product, str(order_vol) + "x", ask)
                        orders.append(Order(product, ask, order_vol))

                undercut_market_ask = best_market_ask - 1
                undercut_market_bid = best_market_bid + 1

                # Spread = 1
                own_ask = max(undercut_market_ask, lower_bound)
                own_bid = min(undercut_market_bid, upper_bound)

                # Market take
                # if cur_position < self.POSITION_LIMITS[product]:
                #     order_vol = self.POSITION_LIMITS[product] - cur_position    
                #     cur_position += order_vol
                #     print("BUY", product, str(order_vol) + "x", own_ask)
                #     orders.append(Order(product, own_ask, order_vol))

                cur_position = self.positions[product]

                # Construct sell orders
                for bid, vol in order_depth.buy_orders.items():
                    if ((bid >= upper_bound) or (self.positions[product] > 0) and (bid == upper_bound - 1)) and cur_position > -self.POSITION_LIMITS[product]:
                        order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("SELL", product, str(order_vol) + "x", bid)
                        orders.append(Order(product, bid, order_vol))

                # if cur_position > -self.POSITION_LIMITS[product]:
                #     order_vol = max(-self.POSITION_LIMITS[product], -self.POSITION_LIMITS[product] - cur_position)
                #     cur_position += order_vol
                #     print("SELL", product, str(order_vol) + "x", own_bid)
                #     orders.append(Order(product, own_bid, order_vol))

            result[product] = orders
    
        traderData = "SAMPLE" # String value holding Trader state data required. It will be delivered as TradingState.traderData on next execution.
        
        conversions = 1
        return result, conversions, traderData