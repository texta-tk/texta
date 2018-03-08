from scipy.stats import beta
import numpy as np

__all__ = ['aggregate_ranks']


def betascores(r):
    x = np.asarray(r, np.float)
    n = x.size
    x.sort()
    p = beta.cdf(x=x, a=np.arange(1, n + 1), b=np.arange(n, 0, -1))
    return p


def rhoscores(r):
    x = betascores(r)
    rho = min(x.min() * x.size, 1)
    return rho


def rank_matrix(glist):
    unique_elements = set()
    for l in glist:
        unique_elements.update(l)

    names = list(unique_elements)
    names.sort()
    ncol = len(glist)
    nrow = len(unique_elements)

    N = nrow
    rmat = np.ones(dtype=np.float, shape=(nrow, ncol))

    # This is the most obvious candidate for optimizing.
    # For loops should be rewritten to numpy array indexing operations
    for col in range(ncol):
        rows = [names.index(i) for i in glist[col]]
        for ind, row in enumerate(rows):
            rmat[row, col] = (1.0 + ind) / N

    return rmat, names


def aggregate_ranks(glist):
    """
    Args:
        glist (list of lists):
    Returns:
        sorted list of (item, score) tuples
        lower score is better.
    """
    rmat, names = rank_matrix(glist)
    return sorted(zip(names, (rhoscores(row) for row in rmat)), key=lambda x: x[1])

