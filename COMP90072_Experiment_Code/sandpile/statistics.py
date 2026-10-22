"""Dependent-sample summaries and normalized discrete likelihoods.

Likelihoods describe marginals, not an IID time-series law. No standard KS
p-values are reported. See Clauset et al. (2009), doi:10.1137/070710111.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import t


def mean_interval(values):
    """Mean and 95% Student-t interval across independent replicates/blocks."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2 or not np.all(np.isfinite(x)):
        return {
            "mean": float(x.mean()) if len(x) else None,
            "low": None,
            "high": None,
            "n": len(x),
        }
    center = float(x.mean())
    half = float(t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))
    return {"mean": center, "low": center - half, "high": center + half, "n": len(x)}


def autocorrelation(values, max_lag=4096):
    """Biased FFT ACF plus initial-positive-pair estimate of integrated time.

    tau=1+2 sum rho; truncate at first nonpositive adjacent-lag pair. This is a
    diagnostic with a finite lag cap, not a proof of mixing or exact ESS.
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    x = x - x.mean()
    if n < 3 or np.dot(x, x) == 0:
        return np.ones(1), 1.0
    transform = np.fft.rfft(x, n=1 << (2 * n - 1).bit_length())
    cov = np.fft.irfft(transform * np.conj(transform))[: min(n, max_lag + 1)]
    rho = cov / cov[0]
    total = 0.0
    for k in range(1, len(rho) - 1, 2):
        pair = rho[k] + rho[k + 1]
        if pair <= 0:
            break
        total += pair
    return rho, float(max(1.0, 1 + 2 * total))


def block_means(x, length):
    """Nonoverlapping complete contiguous block means; remainder is documented."""
    x = np.asarray(x)
    n = len(x) // length
    if n < 2:
        raise ValueError("Need at least two complete blocks")
    return x[: n * length].reshape(n, length).mean(axis=1)


def histogram(values):
    """Exact integer PMF/CCDF over observed support, normalized with all input."""
    x = np.asarray(values)
    if len(x) == 0:
        return np.array([], dtype=int), np.array([]), np.array([])
    if not np.issubdtype(x.dtype, np.integer):
        raise ValueError("Integer observations required")
    support, counts = np.unique(x, return_counts=True)
    pmf = counts / counts.sum()
    ccdf = np.cumsum(pmf[::-1])[::-1]
    return support, pmf, ccdf


def log_binned(values, edges):
    """Display density: count divided by total sample size and actual bin width."""
    counts, bins = np.histogram(values, bins=edges)
    return counts / (len(values) * np.diff(bins))


def discrete_fit(values, xmin, xmax, model="power", minimum_count=100):
    """Fit a normalized discrete marginal on the inclusive range [xmin, xmax].

    power uses x**(-alpha); cutoff adds exp(-lambda*x); exponential fixes alpha=0.
    The scaled parameter beta=lambda*xmax improves numerical conditioning. Alpha
    may be negative because the fitted support is finite. Counts of the original
    integers enter the likelihood; plotted bins do not enter the fit.

    The optimizer uses several starts for cutoff fits and checks a projected
    gradient before accepting a result. KS is a descriptive CDF discrepancy. Neither
    that discrepancy nor the in-sample log score is a calibrated goodness-of-fit test.
    """
    if xmin < 1 or xmax <= xmin:
        raise ValueError("Invalid support")
    raw = np.asarray(values)
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("Integer observations required")
    x = raw[(raw >= xmin) & (raw <= xmax)]
    base = {"model": model, "xmin": int(xmin), "xmax": int(xmax), "n": len(x)}
    if len(x) < minimum_count or len(np.unique(x)) < 3:
        return {**base, "status": "sparse_or_degenerate"}
    support = np.arange(xmin, xmax + 1, dtype=float)
    # Centering features changes the normalizing constant, not the fitted PMF.
    features = np.column_stack([np.log(support / xmin), (support - xmin) / xmax])
    observed = np.array([np.log(x / xmin).mean(), ((x - xmin) / xmax).mean()])
    if model == "power":
        select = [0]
    elif model == "exponential":
        select = [1]
    elif model == "cutoff":
        select = [0, 1]
    else:
        raise ValueError("Unknown model")
    F = features[:, select]
    target = observed[select]

    def objective(theta):
        lp = -F @ theta
        logz = logsumexp(lp)
        p = np.exp(lp - logz)
        return float(theta @ target + logz), target - p @ F

    bounds = [(-10.0, 10.0) if k == 0 else (0.0, 100000.0) for k in select]
    starts = [
        [1.0] if model == "power" else [max(1.0, xmax / max(1.0, x.mean() - xmin))]
    ]
    if model == "cutoff":
        starts = [[1.0, 1.0], [0.0, xmax / max(1.0, x.mean() - xmin)], [2.0, 0.0]]
    solutions = [
        minimize(
            objective,
            start,
            jac=True,
            method="L-BFGS-B",
            bounds=bounds,
            options={"ftol": 1e-13, "gtol": 1e-9, "maxiter": 500},
        )
        for start in starts
    ]
    successful = [r for r in solutions if r.success]
    result = min(successful or solutions, key=lambda z: z.fun)
    # The objective is convex. Verify its bound-constrained first-order condition
    # independently of the optimizer's success flag; retain failed-start counts.
    gradient = objective(result.x)[1].copy()
    for k, (lo, hi) in enumerate(bounds):
        if result.x[k] <= lo + 1e-7:
            gradient[k] = min(0.0, gradient[k])
        if result.x[k] >= hi - 1e-7:
            gradient[k] = max(0.0, gradient[k])
    gradient_error = float(np.max(np.abs(gradient)))
    theta = np.zeros(2)
    theta[select] = result.x
    lp = -features @ theta
    lp -= logsumexp(lp)
    pmf = np.exp(lp)
    counts = np.bincount(x - xmin, minlength=len(support))
    empirical = np.cumsum(counts) / len(x)
    cdf = np.cumsum(pmf)
    ks = float(np.max(np.abs(empirical - cdf)))
    boundary = any(
        abs(value - lo) < 1e-5 or abs(value - hi) < 1e-5
        for value, (lo, hi) in zip(result.x, bounds)
    )
    return {
        **base,
        "status": "ok"
        if result.success and gradient_error < 1e-6
        else "optimizer_failed",
        "alpha": float(theta[0]),
        "lambda": float(theta[1] / xmax),
        "log_likelihood": float(np.dot(counts, lp)),
        "KS": ks,
        "at_boundary": boundary,
        "optimizer_message": str(result.message),
        "projected_gradient_inf": gradient_error,
        "unsuccessful_starts": sum(not r.success for r in solutions),
    }


def fitted_pmf(fit):
    x = np.arange(fit["xmin"], fit["xmax"] + 1)
    logp = -fit["alpha"] * np.log(x) - fit["lambda"] * x
    return x, np.exp(logp - logsumexp(logp))


def log_scores(values, fit):
    """Per original event score; zero outside fitting support, mask returned."""
    x, pmf = fitted_pmf(fit)
    raw = np.asarray(values)
    keep = (raw >= x[0]) & (raw <= x[-1])
    scores = np.zeros(len(raw))
    scores[keep] = np.log(np.maximum(pmf[raw[keep] - x[0]], np.finfo(float).tiny))
    return scores, keep
