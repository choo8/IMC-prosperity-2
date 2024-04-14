from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import json
import statistics

class Trader:
    POSITION_LIMITS = {
        "AMETHYSTS" : 20,
        "STARFRUIT": 20,
        "ORCHIDS": 100
    }

    positions = {
        "AMETHYSTS": 0,
        "STARFRUIT": 0,
        "ORCHIDS": 0
    }

    # Linear regression parameters trained on data from days -2, -1 and 0
    starfruit_coef = [0.19276398, 0.22111366, 0.24350053, 0.34038018]
    starfruit_intercept = 11.302935408693884

    # Cache latest 4 midprice of best_ask and best_bid every iteration
    starfruit_cache = []
    starfruit_spread_cache = []

    # Linear regression parameters trained on data from days -1, 0 and 1
    orchid_coef = [-0.00390237, 0.01665644, -0.01671059, 1.00357441, 0.00354741, -0.0102079, 0.01344986, -0.00677758, -0.20678414, 0.79699544, -1.000907, 0.4123604]
    orchid_intercept = 0.2517364571167491

    # Cache latest 4 values for orchid midprice, sunlight and humidity
    orchid_cache = []
    sunlight_cache = []
    humidity_cache = []

    # Cache cost
    orchid_cost = 0

    def compute_vwap(self, order_depth):
        total_ask, total_bid = 0, 0
        ask_vol, bid_vol = 0, 0

        for ask, vol in order_depth.sell_orders.items():
            total_ask += ask * abs(vol)
            ask_vol += abs(vol)

        for bid, vol in order_depth.buy_orders.items():
            total_bid += bid * vol
            bid_vol += vol

        vwap_ask = total_ask / ask_vol
        vwap_bid = total_bid / bid_vol

        return (vwap_ask + vwap_bid) / 2

    def compute_starfruit_price(self):
        price = self.starfruit_intercept
        
        for idx, cached_price in enumerate(self.starfruit_cache):
            price += self.starfruit_coef[idx] * cached_price
        
        return int(round(price))
    
    def compute_orchid_price(self):
        price = self.orchid_intercept

        for idx, cached_price in enumerate(self.orchid_cache):
            price += self.orchid_coef[idx] * cached_price

        for idx, cached_sunlight in enumerate(self.sunlight_cache):
            price += self.orchid_coef[4 + idx] * cached_sunlight

        for idx, cached_humiditiy in enumerate(self.humidity_cache):
            price += self.orchid_coef[8 + idx] * cached_humiditiy

        return int(round(price))

    def marshalTraderData(self) -> str: 
        return json.dumps({"starfruit_cache": self.starfruit_cache, "starfruit_spread_cache": self.starfruit_spread_cache, "orchid_cache": self.orchid_cache, "orchid_spread_cache": [], "sunlight_cache": self.sunlight_cache, "humidity_cache": self.humidity_cache})

    def unmarshalTraderData(self, state: TradingState): 
        if not state.traderData:
            state.traderData = json.dumps({"starfruit_cache": [], "starfruit_spread_cache": [], "orchid_cache": [], "orchid_spread_cache": [], "sunlight_cache": [], "humidity_cache": []})
        
        traderDataDict = json.loads(state.traderData)
        self.starfruit_cache = traderDataDict["starfruit_cache"]
        self.starfruit_spread_cache = traderDataDict["starfruit_spread_cache"]
        
        self.orchid_cache = traderDataDict["orchid_cache"]
        self.orchid_spread_cache = traderDataDict["orchid_spread_cache"]
        self.sunlight_cache = traderDataDict["sunlight_cache"]
        self.humidity_cache = traderDataDict["humidity_cache"]

    def run(self, state: TradingState):
        # Update positions
        for product, position in state.position.items():
            self.positions[product] = position

        # initialize the caches
        self.unmarshalTraderData(state)

        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            best_market_ask = min(order_depth.sell_orders.keys())
            best_market_bid = max(order_depth.buy_orders.keys())
            
            # market_price = (best_market_ask + best_market_bid) / 2
            market_price = self.compute_vwap(order_depth)

            conversions = 0

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

                if len(self.starfruit_spread_cache) == 4:
                    self.starfruit_spread_cache.pop(0)

                # Cache spread of STARFRUIT orders
                self.starfruit_spread_cache.append(best_market_ask - best_market_bid)

                # Estimate price via linear regression
                if len(self.starfruit_cache) == 4:
                    # acceptable_price = self.compute_starfruit_price()
                    # print(acceptable_price)
                    acceptable_price = round(statistics.fmean(self.starfruit_cache[-5:]))
                    spread = round(statistics.fmean(self.starfruit_spread_cache[-5:]))

                    lower_bound = acceptable_price - (spread // 2)
                    upper_bound = acceptable_price + (spread // 2)
                    # lower_bound = acceptable_price - 1
                    # upper_bound = acceptable_price + 1
                else:
                    # spread = int(1e9)
                    lower_bound = -int(1e9)
                    upper_bound = int(1e9)

                cur_position = self.positions[product]

                # Construct buy orders
                for ask, vol in order_depth.sell_orders.items():
                    if ((ask <= lower_bound) or ((self.positions[product] < 0) and (ask <= lower_bound + (spread // 2)))) and cur_position < self.POSITION_LIMITS[product]:
                    # if ((ask <= lower_bound) or ((self.positions[product] < 0) and (ask == lower_bound + 1))) and cur_position < self.POSITION_LIMITS[product]:
                        order_vol = min(-vol, self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("BUY", product, str(order_vol) + "x", ask)
                        orders.append(Order(product, ask, order_vol))

                undercut_market_ask = best_market_ask - 1
                undercut_market_bid = best_market_bid + 1

                # Spread = 1
                own_ask = max(undercut_market_ask, upper_bound)
                own_bid = min(undercut_market_bid, lower_bound)

                # Market take
                if cur_position < self.POSITION_LIMITS[product]:
                    order_vol = self.POSITION_LIMITS[product] - cur_position
                    cur_position += order_vol
                    print("BUY", product, str(order_vol) + "x", own_bid)
                    orders.append(Order(product, own_bid, order_vol))

                cur_position = self.positions[product]

                # Construct sell orders
                for bid, vol in order_depth.buy_orders.items():
                    if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid >= upper_bound - (spread // 2)))) and cur_position > -self.POSITION_LIMITS[product]:
                    # if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid == upper_bound - 1))) and cur_position > -self.POSITION_LIMITS[product]:
                        order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("SELL", product, str(order_vol) + "x", bid)
                        orders.append(Order(product, bid, order_vol))

                if cur_position > -self.POSITION_LIMITS[product]:
                    order_vol = max(-self.POSITION_LIMITS[product], -self.POSITION_LIMITS[product] - cur_position)
                    cur_position += order_vol
                    print("SELL", product, str(order_vol) + "x", own_ask)
                    orders.append(Order(product, own_ask, order_vol))

            # sunlight less than 7 hour, production decrease 4% for every 10 min
            # humidity ideal 60 - 80, outside fall 2% for every 5% humidity change
            # import / export tarrif
            # storage costs per timestamp: 0.1 seashell

            # each day (1000000 timesteps) = 12 hours
            
            # orchid quality does not deterioriate overnight
            if product == "ORCHIDS":
                if len(self.orchid_cache) == 4:
                    self.orchid_cache.pop(0)

                self.orchid_cache.append(market_price)

                if len(self.orchid_spread_cache) == 4:
                    self.orchid_spread_cache.pop(0)

                self.orchid_spread_cache.append(best_market_ask - best_market_bid)

                conversion_observations = state.observations.conversionObservations[product]

                if len(self.sunlight_cache) == 4:
                    self.sunlight_cache.pop(0)

                self.sunlight_cache.append(conversion_observations.sunlight)

                if len(self.humidity_cache) == 4:
                    self.humidity_cache.pop(0)
                
                self.humidity_cache.append(conversion_observations.humidity)

                if len(self.orchid_cache) == 4:
                    acceptable_price = self.compute_orchid_price()
                    spread = round(statistics.fmean(self.orchid_spread_cache[-5:]))

                    lower_bound = acceptable_price - (spread // 2)
                    upper_bound = acceptable_price + (spread // 2)
                    # lower_bound = acceptable_price - 1
                    # upper_bound = acceptable_price + 1
                else:
                    continue

                # Calculate cost_basis
                own_trades = state.own_trades[product] if product in state.own_trades else []
                cost_basis, traded_quantity = 0, 0

                for trade in own_trades:
                    # Long orchids
                    if trade.buyer == "SUBMISSION":
                        cost_basis += trade.price * trade.quantity
                        traded_quantity += trade.quantity
                    # Short orchids
                    else:
                        cost_basis -= trade.price * trade.quantity
                        traded_quantity += trade.quantity
                
                if traded_quantity > 0:
                    cost_basis /= traded_quantity

                cur_position = self.positions[product]
                print("POSITION", product, cur_position)

                print("CONVERSION_BID", conversion_observations.bidPrice - conversion_observations.exportTariff)
                print("CONVERSION_ASK", conversion_observations.askPrice + conversion_observations.importTariff)
                print("TRANSPORT_FEES", conversion_observations.transportFees)
                # Construct conversions
                if cur_position != 0:
                    # Export conversions
                    if cur_position > 0:
                        conversion_bid = conversion_observations.bidPrice - conversion_observations.exportTariff
                        if conversion_bid - (conversion_observations.transportFees / cur_position) >= cost_basis:
                            print("EXPORT", product, str(cur_position) + "x", conversion_bid)
                            conversions = cur_position
                    # Import conversions
                    else:
                        conversion_ask = conversion_observations.askPrice + conversion_observations.importTariff
                        if conversion_ask + (conversion_observations.transportFees / cur_position) <= -cost_basis:
                            print("IMPORT", product, str(cur_position) + "x", conversion_ask)
                            conversions = -cur_position

                # Construct buy orders
                # for ask, vol in order_depth.sell_orders.items():
                #     print("ASK", ask, "VOL", vol)
                #     if ((ask <= lower_bound) or ((self.positions[product] < 0) and (ask <= lower_bound + (spread // 2)))) and cur_position < self.POSITION_LIMITS[product]:
                #     # if ((ask <= lower_bound) or ((self.positions[product] < 0) and (ask == lower_bound + 1))) and cur_position < self.POSITION_LIMITS[product]:
                #         order_vol = min(-vol, self.POSITION_LIMITS[product] - cur_position)
                #         cur_position += order_vol
                #         print("BUY", product, str(order_vol) + "x", ask)
                #         orders.append(Order(product, ask, order_vol))

                undercut_market_ask = best_market_ask - 1
                undercut_market_bid = best_market_bid + 1

                # Spread = 1
                own_ask = max(undercut_market_ask, upper_bound)
                own_bid = min(undercut_market_bid, lower_bound)

                # Market take
                # if cur_position < self.POSITION_LIMITS[product]:
                #     order_vol = self.POSITION_LIMITS[product] - cur_position
                #     cur_position += order_vol
                #     print("BUY", product, str(order_vol) + "x", undercut_market_bid)
                #     orders.append(Order(product, undercut_market_bid, order_vol))

                cur_position = self.positions[product]

                # Construct sell orders
                # for bid, vol in order_depth.buy_orders.items():
                #     print("BID", ask, "VOL", vol)
                #     if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid >= upper_bound - (spread // 2)))) and cur_position > -self.POSITION_LIMITS[product]:
                #     # if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid == upper_bound - 1))) and cur_position > -self.POSITION_LIMITS[product]:
                #         order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                #         cur_position += order_vol
                #         print("SELL", product, str(order_vol) + "x", bid)
                #         orders.append(Order(product, bid, order_vol))

                if cur_position > -self.POSITION_LIMITS[product]:
                    order_vol = max(-self.POSITION_LIMITS[product], -self.POSITION_LIMITS[product] - cur_position)
                    cur_position += order_vol
                    print("SELL", product, str(order_vol) + "x", undercut_market_ask)
                    orders.append(Order(product, undercut_market_ask, order_vol))

            result[product] = orders
    
        traderData = self.marshalTraderData()
        
        return result, conversions, traderData