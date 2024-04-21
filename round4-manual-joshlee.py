import matplotlib.pyplot as plt
import numpy as np


def plot_expected_profit(b2_list):
    expected_profit = []
    for b2 in b2_list:
        x = np.array(range(900,1001))
        y = (1/10.*x**2 - 180*x + 81000 - 1/10000.*x**3 + 9/50.*x**2 - 81*x - (1000-b2)*80 \
            - (1000-b2)/10000.*x**2 + 9*(1000-b2)/50.*x)
        plt.plot(x, y, label='Average second bid is ' + str(b2))
        plt.xlim(900,1000)
        plt.ylim(0,100)
        plt.ylabel('Expected profit')
        plt.xlabel('First bid')
        expected_profit.append(y)
        #plt.legend()
    plt.show()

    ep_arr = np.array(expected_profit)
    mean_prof = np.mean(ep_arr, axis=0)
    mean_prof = mean_prof.tolist()
    print(mean_prof.index(max(mean_prof)))
    plt.plot(x, mean_prof)
    plt.show()

if __name__ == '__main__':
    b2_list = range(940, 960, 1)
    plot_expected_profit(b2_list)
