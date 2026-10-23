/* FIFO stabilization for the validated array interface in fast.py.
 *
 * Each queue visit performs floor(height / 4) consecutive legal topplings.
 * The Abelian property makes their order immaterial (Jarai 2018, Theorem 2.3).
 *
 * Status codes: 0 success, 1 allocation failure, 2 toppling limit exceeded,
 * 3 unstable/negative checkpoint height, 4 checkpoint mass mismatch.
 * On failure, fast.py discards this chunk's working copy of the grid.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static int64_t absv(int64_t value) { return value < 0 ? -value : value; }
static int64_t minimum(int64_t left, int64_t right) {
    return left < right ? left : right;
}

int simulate(int64_t rows, int64_t cols, int cylinder, int64_t *heights,
             const int64_t *neighbours, const int64_t *sources,
             int64_t event_count, int64_t grains_per_event,
             int64_t event_offset, int64_t checkpoint_stride,
             int64_t toppling_limit, int64_t *event_records,
             int64_t *height_counts, int64_t *last_odometer, int scan_initial) {
    /* At most one queue entry per site; one spare slot distinguishes full/empty. */
    const int64_t site_count = rows * cols, queue_capacity = site_count + 1;
    int64_t *queue = calloc(queue_capacity, sizeof(int64_t));
    int64_t *odometer = calloc(site_count, sizeof(int64_t));
    int64_t *event_stamp = calloc(site_count, sizeof(int64_t));
    unsigned char *queued = calloc(site_count, sizeof(unsigned char));
    if (!queue || !odometer || !event_stamp || !queued) {
        free(queue);
        free(odometer);
        free(event_stamp);
        free(queued);
        return 1;
    }

    int64_t mass = 0, checkpoint_index = 0;
    for (int64_t site = 0; site < site_count; site++) mass += heights[site];
    int status = 0;
    for (int64_t event = 0; event < event_count; event++) {
        int64_t head = 0, tail = 0, topplings = 0, area = 0, loss = 0,
                reach = 0, boundary_distance = site_count;
        const int64_t *event_sources = sources + event * grains_per_event;

        /* Increment one source at a time so repeated batch locations accumulate. */
        for (int64_t index = 0; index < grains_per_event; index++) {
            int64_t site = event_sources[index], row = site / cols, column = site % cols;
            heights[site]++;
            int64_t source_distance = minimum(row, rows - 1 - row);
            if (!cylinder)
                source_distance = minimum(source_distance, minimum(column, cols - 1 - column));
            boundary_distance = minimum(boundary_distance, source_distance);
        }

        /* Production starts stable. Only single-event validation needs a scan. */
        if (scan_initial && event == 0) {
            for (int64_t site = 0; site < site_count; site++) if (heights[site] >= 4) {
                queue[tail] = site;
                tail = (tail + 1) % queue_capacity;
                queued[site] = 1;
            }
        } else {
            for (int64_t index = 0; index < grains_per_event; index++) {
                int64_t site = event_sources[index];
                if (heights[site] >= 4 && !queued[site]) {
                    queue[tail] = site;
                    tail = (tail + 1) % queue_capacity;
                    queued[site] = 1;
                }
            }
        }

        while (head != tail) {
            int64_t site = queue[head];
            head = (head + 1) % queue_capacity;
            queued[site] = 0;
            int64_t bulk_count = heights[site] / 4;

            /* A timestamp resets just the sites visited in this event. It also
             * lets area and reach be counted once per site, despite repeat visits.
             */
            if (event_stamp[site] != event + 1) {
                event_stamp[site] = event + 1;
                odometer[site] = 0;
                area++;
                int64_t distance = rows + cols;
                for (int64_t index = 0; index < grains_per_event; index++) {
                    int64_t row_distance = absv(site / cols - event_sources[index] / cols);
                    int64_t column_distance = absv(site % cols - event_sources[index] % cols);
                    if (cylinder) column_distance = minimum(column_distance, cols - column_distance);
                    distance = minimum(distance, row_distance + column_distance);
                }
                if (distance + 1 > reach) reach = distance + 1;
            }
            heights[site] -= 4 * bulk_count;
            odometer[site] += bulk_count;
            topplings += bulk_count;
            if (topplings > toppling_limit) { status = 2; goto cleanup; }

            /* A -1 destination is a sink; a wrapped horizontal link is internal. */
            for (int index = 0; index < 4; index++) {
                int64_t destination = neighbours[4 * site + index];
                if (destination < 0) loss += bulk_count;
                else {
                    heights[destination] += bulk_count;
                    if (heights[destination] >= 4 && !queued[destination]) {
                        queue[tail] = destination;
                        tail = (tail + 1) % queue_capacity;
                        queued[destination] = 1;
                    }
                }
            }
        }

        mass += grains_per_event - loss;
        event_records[event * 6] = topplings;
        event_records[event * 6 + 1] = area;
        event_records[event * 6 + 2] = loss;
        event_records[event * 6 + 3] = reach;
        event_records[event * 6 + 4] = mass;
        event_records[event * 6 + 5] = boundary_distance;

        /* Checkpoint histograms independently rescan the stable grid and mass.
         * The wrapper also checks final grid mass and all event balance records.
         */
        if ((event_offset + event + 1) % checkpoint_stride == 0) {
            int64_t check_mass = 0;
            for (int64_t site = 0; site < site_count; site++) {
                if (heights[site] < 0 || heights[site] > 3) { status = 3; goto cleanup; }
                height_counts[checkpoint_index * 4 + heights[site]]++;
                check_mass += heights[site];
            }
            if (check_mass != mass) { status = 4; goto cleanup; }
            checkpoint_index++;
        }
    }
    for (int64_t site = 0; site < site_count; site++)
        last_odometer[site] = (event_stamp[site] == event_count ? odometer[site] : 0);

cleanup:
    free(queue);
    free(odometer);
    free(event_stamp);
    free(queued);
    return status;
}
