import numpy as np
import seaborn as sbn
from collections import defaultdict
from scipy.stats import mode, itemfreq
from scipy import delete
from sklearn.metrics import confusion_matrix
import matplotlib as mpl

mpl.use('Agg')
import matplotlib.pyplot as plt
from missing_data_imputation import Imputer

plt.rcParams.update({'figure.autolayout': True})

# declare csv headers
x = np.genfromtxt('adult-train-raw', delimiter=', ', dtype=object)

# remove redundant education-number feature
x = delete(x, (4, 14), 1)

# enumerate parameters and instantiate Imputer
imp = Imputer()
missing_data_symbol = '?'
miss_data_cond = lambda x: x == missing_data_symbol
cat_cols = (1, 3, 4, 5, 6, 7, 8, 12)
n_neighbors = 5
miss_data_rows, miss_data_cols = np.where(miss_data_cond(x))

# remove missing data, which we is are MNAR in the ADULT dataset
x = np.delete(x, miss_data_rows, axis=0)
ratios = np.arange(10, 100, 10)

# monotone False must be fixed
monotone = True


def perturbate_data(x, cat_cols, ratio, missing_data_symbol,
                    monotone=False, in_place=False):
    """Perturbs data by substituting existing values with missing data symbol
    such that each feature has a minimum missing data ratio
    """

    def zero():
        return 0

    if in_place:
        data = x
    else:
        data = np.copy(x)

    n_perturbations = int(len(x) * ratio)
    if monotone:
        cat_cols = np.random.choice(cat_cols, int(len(cat_cols) * .3))
        rows = np.random.randint(0, len(data), n_perturbations)
        cols = np.random.choice(cat_cols, n_perturbations)

        data[rows, cols] = missing_data_symbol
        miss_dict = defaultdict(list)
        for (row, col) in np.dstack((rows, cols))[0]:
            miss_dict[col].append(row)
    else:
        # slow version
        row_col_miss = defaultdict(zero)
        miss_dict = defaultdict(list)
        i = 0
        while i < n_perturbations:
            row = np.random.randint(0, len(data))
            col = np.random.choice(cat_cols)

            # proceed if less than half the features are missing
            if row_col_miss[row] < len(cat_cols) * 0.5 and data[row, col] != missing_data_symbol:
                data[row, col] = missing_data_symbol
                row_col_miss[row] += 1
                miss_dict[col].append(row)
                i += 1

    return data, miss_dict


def compute_histogram(data, labels):
    histogram = dict(itemfreq(data))
    for label in labels:
        if label not in histogram:
            histogram[label] = .0
    return histogram


def compute_error_rate(y, y_hat, feat_imp_ids):
    error_rate = {}
    for col, ids in feat_imp_ids.items():
        errors = sum(y[ids, col] != y_hat[ids, col])
        error_rate[col] = errors / float(len(ids))

    return error_rate


# helper function to plot histograms
def plot_histogram(freq_data, labels, axes, axis, width, title,
                   color_mapping):
    n_methods = len(freq_data.keys())
    labels = sorted(freq_data.values()[0].keys())
    bins = np.arange(len(labels))

    for i in range(n_methods):
        key = sorted(freq_data.keys())[i]
        offset = i * 2 * width / float(n_methods)
        values = [freq_data[key][label] for label in labels]
        axes.flat[axis].bar(bins + offset, values,
                            width, label=key,
                            color=plt.cm.Set1(color_mapping[key]),
                            align='center')

    axes.flat[axis].set_xlim(bins[0] - 0.5, bins[-1] + width + 0.5)
    axes.flat[axis].set_title(title)
    axes.flat[axis].set_xticks(bins + width)
    axes.flat[axis].set_xticklabels(labels, rotation=90,
                                    fontsize='small')
    axes.flat[axis].legend(loc='best', prop={'size': 8},
                           shadow=True, fancybox=True)


def plot_confusion_matrix(y, y_predict, axes, axis, title='',
                          normalize=True, add_text=False):
    """Plots a confusion matrix given labels and predicted labels

    Parameters
    ----------
        y: ground truth labels <int array>
        y_predict: predicted labels <int array>
    """

    conf_mat = confusion_matrix(y, y_predict)
    if normalize:
        conf_mat_norm = conf_mat / conf_mat.sum(axis=1).astype(float)[:, np.newaxis]
        conf_mat_norm = np.nan_to_num(conf_mat_norm)

    axes.flat[axis].imshow(conf_mat_norm, cmap=plt.cm.Blues,
                           interpolation='nearest')
    if axis < axes.shape[1]:
        axes.flat[axis].set_title(title)

    # add text to confusion matrix
    if add_text:
        for x in range(conf_mat.shape[0]):
            for y in range(conf_mat.shape[0]):
                if conf_mat[x, y] > 0:
                    axes.flat[axis].annotate(str(conf_mat[x, y]),
                                             xy=(y, x),
                                             horizontalalignment='center',
                                             verticalalignment='center')


for ratio in ratios:
    print('Experiments on {}% missing data'.format(ratio))
    pert_data, feat_imp_ids = perturbate_data(x, cat_cols, .01 * ratio,
                                              missing_data_symbol,
                                              monotone=monotone)

    miss_data_cols = feat_imp_ids.keys()
    print('Missing data cols {}'.format(miss_data_cols))

    data_dict = {'RawData': pert_data}

    # drop observations with missing variables
    print('imputing with drop')
    data_dict['Drop'] = imp.drop(pert_data, miss_data_cond)

    # replace missing values with random existing values
    print('imputing with random replacement')
    data_dict['RandomReplace'] = imp.replace(pert_data, miss_data_cond)

    # replace missing values with feature summary
    print('imputing with feature summarization (mode)')
    summ_func = lambda x: mode(x)[0]
    data_dict['Mode'] = imp.summarize(pert_data, summ_func, miss_data_cond)

    # replace missing data with predictions using random forest
    print('imputing with Random Forest')
    data_dict['RandomForest'] = imp.predict(pert_data, cat_cols, miss_data_cond)

    # replace missing data with values obtained after factor analysis
    print('imputing with PCA')
    data_dict['PCA'] = imp.factor_analysis(pert_data, cat_cols, miss_data_cond)

    # replace missing data with knn
    print('imputing with K-Nearest Neighbors')
    data_dict['KNN'] = imp.knn(pert_data, n_neighbors, np.mean, miss_data_cond,
                               cat_cols)

    conf_methods = ['RandomReplace', 'Mode', 'RandomForest', 'PCA', 'KNN']
    methods = ['RawData', 'Drop', 'RandomReplace', 'Mode', 'RandomForest',
               'PCA', 'KNN']

    color_mapping = {}
    for i in range(len(methods)):
        color_mapping[methods[i]] = (i + 1) / float(len(methods))

    ###########################
    # plot confusion matrices #
    ###########################
    fig, axes = plt.subplots(len(miss_data_cols), len(conf_methods),
                             figsize=(8, 8))
    axis = 0
    for col in miss_data_cols:
        for key in conf_methods:
            plot_confusion_matrix(x[:, col], data_dict[key][:, col], axes, axis,
                                  key)
            axis += 1

    plt.savefig('images/mcar_mono_{}_conf_matrix_miss_ratio_{}.png'.format(monotone, ratio), dpi=300)

    #######################
    # compute error rates #
    #######################
    error_rates = {}
    for method in conf_methods:
        error_rates[method] = compute_error_rate(x, data_dict[method],
                                                 feat_imp_ids)

    # set plot params
    fig, axes = plt.subplots(1 + (len(miss_data_cols) / 3), 3, figsize=(16, 9))
    width = .25

    ###############################
    # compute and plot histograms #
    ###############################
    for i in range(len(miss_data_cols)):
        col = miss_data_cols[i]
        labels = np.unique(x[:, col])
        freq_data = {}
        for key, data in data_dict.items():
            freq_data[key] = compute_histogram(data[:, col], labels)
        plot_histogram(freq_data, labels, axes, i, width, col, color_mapping)

    plt.savefig('images/mcar_mono_{}_dist_ratio_{}.png'.format(monotone, ratio), dpi=300)

    ########################
    # plot error rate bars #
    ########################
    fig, axes = plt.subplots(1, 1, figsize=(10, 5))
    n_methods = len(error_rates.keys())
    bins = np.arange(len(feat_imp_ids))
    width = .25

    for i in range(n_methods):
        key = sorted(error_rates.keys())[i]
        offset = i * width / float(n_methods)
        values = [error_rates[key][feat] for feat in sorted(error_rates[key])]
        axes.bar(bins + offset, values, width, label=key,
                 color=plt.cm.Set1(color_mapping[key]),
                 align='center')
    axes.set_xlim(bins[0] - 0.5, bins[-1] + width + 0.5)
    axes.set_xticks(bins + width)
    axes.set_xticklabels(sorted(feat_imp_ids.keys()))
    axes.legend(loc='best', prop={'size': 8},
                shadow=True, fancybox=True)
    axes.set_title('Error rates')

    plt.savefig('images/mcar_mono_{}_error_miss_ratio_{}.png'.format(monotone, ratio), dpi=300)
