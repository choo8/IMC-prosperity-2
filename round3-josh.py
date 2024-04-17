from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
from collections import OrderedDict
import json
import statistics

class Trader:
    POSITION_LIMITS = {
        "AMETHYSTS" : 20,
        "STARFRUIT": 20,
        "ORCHIDS": 100,
        "CHOCOLATE": 250,
        "STRAWBERRIES": 350,
        "ROSES": 60,
        "GIFT_BASKET": 60
    }

    positions = {
        "AMETHYSTS": 0,
        "STARFRUIT": 0,
        "ORCHIDS": 0,
        "CHOCOLATE": 0,
        "STRAWBERRIES": 0,
        "ROSES": 0,
        "GIFT_BASKET": 0
    }

    # Linear regression parameters trained on data from days -2, -1 and 0
    starfruit_coef = [0.19276398, 0.22111366, 0.24350053, 0.34038018]
    starfruit_intercept = 11.302935408693884

    # Cache latest 4 midprice of best_ask and best_bid every iteration
    starfruit_cache = []
    starfruit_spread_cache = []

    # Linear regression parameters trained on data from days -1, 0 and 1
    orchid_coef = [-2.16359544e-03, 9.82450923e-03, -1.23079864e-02, 1.00442531e+00, 8.65723543e+00, -2.78822090e+01, 2.97898002e+01, -1.05648098e+01, 2.34006780e+02, -1.29033746e+03, 1.87744151e+03, -8.21110222e+02]
    orchid_intercept = 0.14551195562876273

    # Cache latest 4 values for orchid midprice, sunlight and humidity
    orchid_cache = []
    sunlight_cache = []
    humidity_cache = []

    # To calculate cost basis of shorted ORCHIDS
    # orchid_cost_basis = 0
    # orchid_last_trade = -1

    gift_basket_std = 75

    etf_returns = []
    assets_returns = []

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
    
    def compute_basket_orders(self, order_depths):
        products = ["CHOCOLATE", "STRAWBERRIES", "ROSES", "GIFT_BASKET"]
        mid_prices, orders = {}, {"GIFT_BASKET": []}

        for product in products:
            best_market_ask = min(order_depths[product].sell_orders.keys())
            best_market_bid = max(order_depths[product].buy_orders.keys())

            worst_market_ask = max(order_depths[product].sell_orders.keys())
            worst_market_bid = min(order_depths[product].buy_orders.keys())

            mid_prices[product] = (best_market_ask + best_market_bid) / 2
            
            # Size orders to 10% of position limits
            # buy_vol, sell_vol = 0, 0
            # for bid, vol in order_depths[product].buy_orders.items():
            #     buy_vol += vol
            #     if buy_vol >= self.POSITION_LIMITS[product] / 10:
            #         break

            # for ask, vol in order_depths[product].sell_orders.items():
            #     sell_vol += vol
            #     if sell_vol >= self.POSITION_LIMITS[product] / 10:
            #         break

        # Calculate residual term, how much spread deviates from 0
        buy_residual = mid_prices["GIFT_BASKET"] - 4 * mid_prices["CHOCOLATE"] - 6 * mid_prices["STRAWBERRIES"] - mid_prices["ROSES"] - 380
        sell_residual = mid_prices["GIFT_BASKET"] - 4 * mid_prices["CHOCOLATE"] - 6 * mid_prices["STRAWBERRIES"] - mid_prices["ROSES"] - 380

        trade_at = self.gift_basket_std * 0.5
        close_at = self.gift_basket_std * -1000

        gift_basket_pos = self.positions["GIFT_BASKET"]
        gift_basket_neg = self.positions["GIFT_BASKET"]

        gift_basket_buy_signal = False
        gift_basket_sell_signal = False

        # if self.positions["GIFT_BASKET"] == self.POSITION_LIMITS["GIFT_BASKET"]:
        #     self.continue_buy_gift_basket_unfill = False
        # if self.positions["GIFT_BASKET"] == -self.POSITION_LIMITS["GIFT_BASKET"]:
        #     self.continue_sell_gift_basket_unfill = False

        do_gift_basket = False

        if sell_residual > trade_at:
            vol = self.positions["GIFT_BASKET"] + self.POSITION_LIMITS["GIFT_BASKET"]
            # self.continue_buy_gift_basket_unfill = False # Don't need to buy GIFT_BASKET
            if vol > 0:
                do_gift_basket = True
                gift_basket_sell_signal = True
                orders["GIFT_BASKET"].append(Order("GIFT_BASKET", worst_market_bid, -vol))
                # self.continue_sell_gift_basket_unfill += 2
                gift_basket_neg -= vol
        elif buy_residual < -trade_at:
            vol = self.positions["GIFT_BASKET"] - self.POSITION_LIMITS["GIFT_BASKET"]
            # self.continue_sell_gift_basket_unfill = False
            if vol > 0:
                do_gift_basket = True
                gift_basket_buy_signal = True
                orders["GIFT_BASKET"].append(Order("GIFT_BASKET", worst_market_ask, vol))
                # self.continue_buy_gift_basket_unfill += 2
                gift_basket_pos += vol

        return orders

    def compute_basket_orders2(self, state: TradingState):
        products = ["CHOCOLATE", "STRAWBERRIES", "ROSES", "GIFT_BASKET"]
        positions, buy_orders, sell_orders, best_bids, best_asks, prices, orders = {}, {}, {}, {}, {}, {}, {"GIFT_BASKET": []}

        for product in products:
            positions[product] = state.position[product] if product in state.position else 0

            buy_orders[product] = state.order_depths[product].buy_orders
            sell_orders[product] = state.order_depths[product].sell_orders

            best_bids[product] = max(buy_orders[product].keys())
            best_asks[product] = min(sell_orders[product].keys())

            prices[product] = (best_bids[product] + best_asks[product]) / 2.0

        estimated_price = 4.0 * prices["CHOCOLATE"] + 6.0 * prices["STRAWBERRIES"] + prices["ROSES"]

        price_nav_ratio = prices["GIFT_BASKET"] / estimated_price

        self.etf_returns.append(prices["GIFT_BASKET"])
        self.assets_returns.append(estimated_price)

        if len(self.etf_returns) < 2 or len(self.assets_returns) < 2:
            return orders

        etf_rolling_mean = statistics.fmean(self.etf_returns[-10:])
        etf_rolling_std = statistics.stdev(self.etf_returns[-10:])

        assets_rolling_mean = statistics.fmean(self.assets_returns[-10:])
        assets_rolling_std = statistics.stdev(self.assets_returns[-10:])

        etf_z_score = (self.etf_returns[-1] - etf_rolling_mean) / etf_rolling_std
        assets_z_score = (self.assets_returns[-1] - assets_rolling_mean) / assets_rolling_std

        z_score_diff = etf_z_score - assets_z_score

        # GIFT_BASKET undervalued
        if z_score_diff < -2:
            etf_best_ask_vol = sell_orders["GIFT_BASKET"][best_asks["GIFT_BASKET"]]
            chocolate_best_bid_vol = buy_orders["CHOCOLATE"][best_bids["CHOCOLATE"]]
            strawberries_best_bid_vol = buy_orders["STRAWBERRIES"][best_bids["STRAWBERRIES"]]
            roses_best_bid_vol = buy_orders["ROSES"][best_bids["ROSES"]]

            limit_mult = min(-etf_best_ask_vol, round(chocolate_best_bid_vol / 4), round(strawberries_best_bid_vol / 6), roses_best_bid_vol)

            print("BUY", "GIFT_BASKET", str(limit_mult) + "x", best_asks["GIFT_BASKET"])
            orders["GIFT_BASKET"].append(Order("GIFT_BASKET", best_asks["GIFT_BASKET"], limit_mult))
        # GIFT_BASKET overvalued
        elif z_score_diff > 2:
            etf_best_bid_vol = buy_orders["GIFT_BASKET"][best_bids["GIFT_BASKET"]]
            chocolate_best_ask_vol = sell_orders["CHOCOLATE"][best_asks["CHOCOLATE"]]
            strawberries_best_ask_vol = sell_orders["STRAWBERRIES"][best_asks["STRAWBERRIES"]]
            roses_best_ask_vol = sell_orders["ROSES"][best_asks["ROSES"]]

            limit_mult = min(etf_best_bid_vol, round(-chocolate_best_ask_vol / 4), round(-strawberries_best_ask_vol / 6), -roses_best_ask_vol)
            
            print("SELL", "GIFT_BASKET", str(limit_mult) + "x", best_bids["GIFT_BASKET"])
            orders["GIFT_BASKET"].append(Order("GIFT_BASKET", best_bids["GIFT_BASKET"], -limit_mult))

        return orders

    def marshalTraderData(self) -> str: 
        return json.dumps({"starfruit_cache": self.starfruit_cache, "starfruit_spread_cache": self.starfruit_spread_cache, "orchid_cache": self.orchid_cache, "orchid_spread_cache": [], "sunlight_cache": self.sunlight_cache, "humidity_cache": self.humidity_cache, "etf_returns": self.etf_returns, "assets_returns": self.assets_returns})

    def unmarshalTraderData(self, state: TradingState): 
        if not state.traderData:
            state.traderData = json.dumps({"starfruit_cache": [], "starfruit_spread_cache": [], "orchid_cache": [], "orchid_spread_cache": [], "sunlight_cache": [], "humidity_cache": [], "etf_returns": [], "assets_returns": []})
        
        traderDataDict = json.loads(state.traderData)
        self.starfruit_cache = traderDataDict["starfruit_cache"]
        self.starfruit_spread_cache = traderDataDict["starfruit_spread_cache"]
        
        self.orchid_cache = traderDataDict["orchid_cache"]
        self.orchid_spread_cache = traderDataDict["orchid_spread_cache"]
        self.sunlight_cache = traderDataDict["sunlight_cache"]
        self.humidity_cache = traderDataDict["humidity_cache"]

        self.etf_returns = traderDataDict["etf_returns"]
        self.assets_returns = traderDataDict["assets_returns"]

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
                        # print("BUY", product, str(order_vol) + "x", ask)
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
                    # print("BUY", product, str(order_vol) + "x", ask)
                    orders.append(Order(product, ask, order_vol))

                cur_position = self.positions[product]
        
                # Market make
                for bid, vol in order_depth.buy_orders.items():
                    if ((bid > acceptable_price) or ((self.positions[product] > 0) and (bid == acceptable_price))) and cur_position > -self.POSITION_LIMITS[product]:
                        order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        # print("SELL", product, str(order_vol) + "x", bid)
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
                    # print("SELL", product, str(order_vol) + "x", bid)
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
                        # print("BUY", product, str(order_vol) + "x", ask)
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
                    # print("BUY", product, str(order_vol) + "x", own_bid)
                    orders.append(Order(product, own_bid, order_vol))

                cur_position = self.positions[product]

                # Construct sell orders
                for bid, vol in order_depth.buy_orders.items():
                    if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid >= upper_bound - (spread // 2)))) and cur_position > -self.POSITION_LIMITS[product]:
                    # if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid == upper_bound - 1))) and cur_position > -self.POSITION_LIMITS[product]:
                        order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        # print("SELL", product, str(order_vol) + "x", bid)
                        orders.append(Order(product, bid, order_vol))

                if cur_position > -self.POSITION_LIMITS[product]:
                    order_vol = max(-self.POSITION_LIMITS[product], -self.POSITION_LIMITS[product] - cur_position)
                    cur_position += order_vol
                    # print("SELL", product, str(order_vol) + "x", own_ask)
                    orders.append(Order(product, own_ask, order_vol))

            # sunlight less than 7 hour, production decrease 4% for every 10 min
            # humidity ideal 60 - 80, outside fall 2% for every 5% humidity change
            # import / export tarrif
            # storage costs per timestamp: 0.1 seashell

            # each day (1000000 timesteps) = 12 hours
            
            # orchid quality does not deterioriate overnight
            elif product == "ORCHIDS":
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

                own_trades = state.own_trades[product] if product in state.own_trades else []

                # Re-calculate cost_basis
                # if len(own_trades) != 0:
                #     self.shorted_orchid = 0

                #     new_cost_basis, new_quantity = 0, 0

                #     for trade in own_trades:
                #         if trade.seller == "SUBMISSION" and trade.timestamp > self.orchid_last_trade:
                #             print(trade)
                #             new_cost_basis += trade.price * trade.quantity
                #             new_quantity += trade.quantity

                #     self.orchid_last_trade = own_trades[0].timestamp
                    
                #     old_quantity = new_quantity - self.positions[product]
                #     new_cost_basis += abs(self.orchid_cost_basis) * old_quantity
                #     new_cost_basis /= self.positions[product]
                #     self.orchid_cost_basis = new_cost_basis

                # own_trades = state.own_trades[product] if product in state.own_trades else []
                # cost_basis, traded_quantity = 0, 0

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
                print("COST_BASIS", cost_basis)

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
                            cur_position = 0 # All current positions converted

                    # Import conversions
                    else:
                        conversion_ask = conversion_observations.askPrice + conversion_observations.importTariff
                        if conversion_ask + (conversion_observations.transportFees / cur_position) <= -cost_basis:
                            print("IMPORT", product, str(cur_position) + "x", conversion_ask)
                            conversions = -cur_position
                            cur_position = 0 # All current positions converted

                # Construct buy orders
                for ask, vol in order_depth.sell_orders.items():
                    print("ASK", ask, "VOL", vol)
                    # if ((ask <= lower_bound) or ((self.positions[product] < 0) and (ask <= lower_bound + (spread // 2)))) and cur_position < self.POSITION_LIMITS[product]:
                    # if ((ask <= lower_bound) or ((self.positions[product] < 0) and (ask == lower_bound + 1))) and cur_position < self.POSITION_LIMITS[product]:
                    if (ask < cost_basis) and (cur_position < self.POSITION_LIMITS[product]):
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
                # if cur_position < self.POSITION_LIMITS[product]:
                #     order_vol = self.POSITION_LIMITS[product] - cur_position
                #     cur_position += order_vol
                #     print("BUY", product, str(order_vol) + "x", undercut_market_bid)
                #     orders.append(Order(product, undercut_market_bid, order_vol))

                cur_position = self.positions[product]

                # Construct sell orders
                for bid, vol in order_depth.buy_orders.items():
                    print("BID", ask, "VOL", vol)
                    if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid >= upper_bound - (spread // 2)))) and cur_position > -self.POSITION_LIMITS[product]:
                    # if ((bid >= upper_bound) or ((self.positions[product] > 0) and (bid == upper_bound - 1))) and cur_position > -self.POSITION_LIMITS[product]:
                        order_vol = max(-vol, -self.POSITION_LIMITS[product] - cur_position)
                        cur_position += order_vol
                        print("SELL", product, str(order_vol) + "x", bid)
                        orders.append(Order(product, bid, order_vol))

                if cur_position > -self.POSITION_LIMITS[product]:
                    order_vol = max(-self.POSITION_LIMITS[product], -self.POSITION_LIMITS[product] - cur_position)
                    # order_vol = max(int(0.05 * -self.POSITION_LIMITS[product]), -self.POSITION_LIMITS[product] - cur_position) # Buy at most 5% of POSITION_LIMITS
                    cur_position += order_vol
                    print("SELL", product, str(order_vol) + "x", undercut_market_ask)
                    orders.append(Order(product, undercut_market_ask, order_vol))

            result[product] = orders
    
        # 6 strawberry, 4 choc and 1 rose in 1 basket
        # treasure chest 7500 seashells each
        # basket_orders = self.compute_basket_orders(state.order_depths)
        basket_orders = self.compute_basket_orders2(state)

        for product, orders in basket_orders.items():
            result[product] = orders

        traderData = self.marshalTraderData()
        
        return result, conversions, traderData