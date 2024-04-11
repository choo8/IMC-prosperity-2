import pandas as pd
import sys

if __name__ == '__main__':
    df = pd.read_csv(sys.argv[1], delimiter=';')
    df_small = df[['day', 'timestamp', 'product', 'mid_price']]
    df_amethysts = df_small[df_small['product'] == 'AMETHYSTS']
    print(df_amethysts)

    # compute a rolling window of the existing data
    df_window = df_amethysts['mid_price'].rolling(5, min_periods=3, center=True).median()# .round()
    print(df_window)
    df_window.to_csv("out1-median.csv")
    # print(df_window.())
    # print(df_window.min())