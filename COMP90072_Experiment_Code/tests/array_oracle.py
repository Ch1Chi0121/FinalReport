"""Independent validation oracle: no project geometry, metrics or simulator.

Bulk parallel waves move grains by direct array shifts. Summed boundary flux,
odometer geometry and actual array mass are computed here independently.
"""
import numpy as np


def stabilize(grid, sources, cylinder=False):
    h = np.array(grid, dtype=np.int64, copy=True)
    rows, cols = h.shape
    source_coordinates = [divmod(int(x), cols) for x in sources]
    previous_mass = int(h.sum())
    for i, j in source_coordinates:
        h[i, j] += 1
    u = np.zeros_like(h)
    loss = 0
    while np.any(h >= 4):
        wave = h // 4
        h -= 4 * wave
        u += wave
        h[1:, :] += wave[:-1, :]
        h[:-1, :] += wave[1:, :]
        loss += int(wave[0, :].sum() + wave[-1, :].sum())
        if cylinder:
            h += np.roll(wave, 1, axis=1) + np.roll(wave, -1, axis=1)
        else:
            h[:, 1:] += wave[:, :-1]
            h[:, :-1] += wave[:, 1:]
            loss += int(wave[:, 0].sum() + wave[:, -1].sum())
    actual_mass = int(h.sum())
    assert actual_mass == previous_mass + len(sources) - loss
    assert np.all((h >= 0) & (h < 4))
    i, j = np.nonzero(u)
    if len(i):
        distance = []
        for si, sj in source_coordinates:
            horizontal = np.abs(j - sj)
            if cylinder:
                horizontal = np.minimum(horizontal, cols - horizontal)
            distance.append(np.abs(i - si) + horizontal)
        reach = 1 + int(np.min(distance, axis=0).max())
    else:
        reach = 0
    boundary = min(
        min(i, rows - 1 - i) if cylinder else min(i, rows - 1 - i, j, cols - 1 - j)
        for i, j in source_coordinates
    )
    event = np.array(
        [u.sum(), len(i), loss, reach, actual_mass, boundary], dtype=np.int64
    )
    return h, u, event
