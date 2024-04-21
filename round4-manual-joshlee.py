import matplotlib.pyplot as plt
import numpy as np


def plot_expected_profit(b2_list, our_b2):
    expected_profit = []
    for b2 in b2_list:
        x = np.array(range(900,1001))
        if our_b2 < b2:
            y = (1000-x)*(1/10000.*x**2 - 9/50.*x + 81) \
                 + (1000-b2)*(1/10000.*our_b2**2 - 9/50.*our_b2 - 1/10000.*x**2 + 9/50.*x)

        else:
            y = (1000-x)*(1/10000.*x**2 - 9/50.*x + 81) + (1000 - our_b2)

        plt.plot(x, y, label='Average second bid is ' + str(b2))
        plt.xlim(900,1000)
        plt.ylim(0,100)
        plt.ylabel('Expected profit')
        plt.xlabel('First bid')
        expected_profit.append(y)
        #plt.legend()
    #plt.show()

    ep_arr = np.array(expected_profit)
    mean_prof = np.mean(ep_arr, axis=0)
    mean_prof = mean_prof.tolist()
    print(mean_prof.index(max(mean_prof)), max(mean_prof), '\n')
    plt.plot(x, mean_prof)
    #plt.show()

if __name__ == '__main__':
    b2_list = range(970, 985, 1)
    for our_b2 in range(967, 990):
        print(our_b2)
        plot_expected_profit(b2_list, our_b2)
