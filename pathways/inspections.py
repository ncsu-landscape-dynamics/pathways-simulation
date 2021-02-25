# Simulation for evaluation of pathways
# Copyright (C) 2018-2021 Vaclav Petras and others (see below)

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.

# You should have received a copy of the GNU General Public License along with
# this program; if not, see https://www.gnu.org/licenses/gpl-2.0.html


"""
Inspections of consignments in pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Kellyn P. Montgomery <kellynmontgomery gmail com>
"""

from __future__ import print_function, division

import math
import random
import types
import weakref
import numpy as np


if not hasattr(weakref, "finalize"):
    from backports import weakref  # pylint: disable=import-error


def inspect_first(consignment):
    """Inspect only the first box in the consignment"""
    if consignment.boxes[0]:
        return False, 1
    return True, 1


def inspect_one_random(consignment):
    """Inspect only one randomly picked box in the consignment"""
    if random.choice(consignment.boxes):
        return False, 1
    return True, 1


def inspect_all(consignment):
    """Inspect all boxes in the consignment"""
    return not is_consignment_contaminated(consignment), consignment.num_boxes


def inspect_first_n(num_boxes, consignment):
    """Inspect only the first n boxes in the consignment

    :param num_boxes: Number of boxes to inspect
    :param consignment: Consignment to inspect
    """
    num_boxes = min(len(consignment.boxes), num_boxes)
    for i in range(num_boxes):
        if consignment.boxes[i]:
            return False, i + 1
    return True, num_boxes


def sample_proportion(config, consignment):
    """Set sample size to sample units from consignment using proportion strategy.
    Return number of units to inspect.

    :param config: Configuration to be used595
    :param consignment: Consignment to be inspected
    """
    unit = config["inspection"]["unit"]
    ratio = config["inspection"]["proportion"]["value"]
    num_items = consignment.num_items
    num_boxes = consignment.num_boxes
    min_boxes = config["inspection"]["min_boxes"]

    if unit in ["item", "items"]:
        n_units_to_inspect = round(ratio * num_items)
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = round(ratio * num_boxes)
        n_units_to_inspect = max(min_boxes, n_units_to_inspect)
        n_units_to_inspect = min(num_boxes, n_units_to_inspect)
    else:
        raise RuntimeError("Unknown sampling unit: {unit}".format(**locals()))
    return n_units_to_inspect


def compute_hypergeometric(detection_level, confidence_level, population_size):
    """Get sample size using hypergeometric distribution

    Compute sample size using hypergeometric distribution based on population
    size (total number of items or boxes in consignment), detection level,
    and confidence level.
    """
    # Equation comes from RBS spreadsheet for calculating hypergeometric
    # sample sizes created by IICA, USDA APHIS PPQ, and NAPPO.
    sample_size = math.ceil(
        (1 - ((1 - confidence_level) ** (1 / (detection_level * population_size))))
        * (population_size - (((detection_level * population_size) - 1) / 2))
    )

    # The computation gives sample size > num boxes when using 1% detection
    # Make max sample size = population size
    sample_size = min(sample_size, population_size)
    return sample_size


def sample_hypergeometric(config, consignment):
    """Set sample size to sample units from consignment using hypergeometric/detection
    level strategy. Return number of units to inspect.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    """
    unit = config["inspection"]["unit"]
    detection_level = config["inspection"]["hypergeometric"]["detection_level"]
    confidence_level = config["inspection"]["hypergeometric"]["confidence_level"]
    num_items = consignment.num_items
    num_boxes = consignment.num_boxes

    if unit in ["item", "items"]:
        n_units_to_inspect = compute_hypergeometric(
            detection_level, confidence_level, num_items
        )
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = compute_hypergeometric(
            detection_level, confidence_level, num_boxes
        )
    else:
        raise RuntimeError("Unknown sampling unit: {unit}".format(**locals()))
    return n_units_to_inspect


def sample_all(config, consignment):
    """Set sample size to sample all units from consignment.
    Return number of units to inspect.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    """
    unit = config["inspection"]["unit"]
    if unit in ["item", "items"]:
        n_units_to_inspect = consignment.num_items
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = consignment.num_boxes
    return n_units_to_inspect


def sample_n(config, consignment):
    """Set sample size to sample fixed number of units from consignment.
    Check if fixed number is <= max units for inspection.
    Return number of units to inspect.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    """
    fixed_n = config["inspection"]["fixed_n"]
    unit = config["inspection"]["unit"]
    within_box_proportion = config["inspection"]["within_box_proportion"]
    items_per_box = consignment.items_per_box
    num_items = consignment.num_items
    num_boxes = consignment.num_boxes
    min_boxes = config["inspection"]["min_boxes"]

    if unit in ["item", "items"]:
        max_items = compute_max_inspectable_items(
            num_items, items_per_box, within_box_proportion
        )
        # Check if max number of items that can be inspected is less than fixed number.
        n_units_to_inspect = min(max_items, fixed_n)
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = fixed_n
        n_units_to_inspect = max(min_boxes, n_units_to_inspect)
        n_units_to_inspect = min(num_boxes, n_units_to_inspect)
    return n_units_to_inspect


def convert_items_to_boxes_fixed_proportion(config, consignment, n_items_to_inspect):
    """Convert number of items to inspect to number of boxes to inspect based on
    the number of items per box and the proportion of items to inspect per box
    specified in the config. Adjust number of boxes to inspect to be at least
    the minimum number of boxes to inspect specified in the config and at most the
    total number of boxes in the consignment.
    Return number of boxes to inspect.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_items_to_inspect: Number of items to inspect defined in sample functions.
    """
    items_per_box = consignment.items_per_box
    within_box_proportion = config["inspection"]["within_box_proportion"]
    min_boxes = config["inspection"]["min_boxes"]
    num_boxes = consignment.num_boxes
    inspect_per_box = int(math.ceil(within_box_proportion * items_per_box))

    n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
    n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
    n_boxes_to_inspect = min(num_boxes, n_boxes_to_inspect)
    return n_boxes_to_inspect


def compute_n_clusters_to_inspect(config, consignment, n_items_to_inspect):
    """Compute number of cluster units (boxes) that need to be opened to achieve item
    sample size when using the cluster selection strategy. Use config within box
    proportion if possible or compute minimum number of items to inspect per box
    required to achieve item sample size.
    Return number of boxes to inspect and number of items to inspect per box.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_items_to_inspect: Number of items to inspect defined by sample functions.
    """
    cluster_selection = config["inspection"]["cluster"]["cluster_selection"]
    items_per_box = consignment.items_per_box
    within_box_proportion = config["inspection"]["within_box_proportion"]
    min_boxes = config["inspection"]["min_boxes"]
    num_boxes = consignment.num_boxes
    num_items = consignment.num_items

    if cluster_selection == "random":
        # Check if within box proportion is high enough to achieve sample size.
        max_items = compute_max_inspectable_items(
            num_items, items_per_box, within_box_proportion
        )
        if max_items >= n_items_to_inspect:
            inspect_per_box = math.ceil(within_box_proportion * items_per_box)
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
        else:
            # If not, divide sample size across number of boxes to get number
            # of items to inspect per box.
            print(
                "Warning: Within box proportion is too low to achieve sample size. "
                "Automatically increasing within box proportion to achieve sample size."
            )
            inspect_per_box = math.ceil(n_items_to_inspect / num_boxes)
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)

    elif cluster_selection == "interval":  # Every nth box, where n = interval
        interval = config["inspection"]["cluster"]["interval"]
        # Maximum num boxes that can be inspected based on interval.
        # Should be at least 1.
        max_boxes = max(1, round(num_boxes / interval))
        # Assumes full boxes, no remainder partial box.
        max_items = max_boxes * (math.ceil(within_box_proportion * items_per_box))
        # Check if within box proportion is high enough and/or interval is
        # low enough to achieve sample size
        if max_items >= n_items_to_inspect:
            inspect_per_box = math.ceil(within_box_proportion * items_per_box)
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
        # If not, divide sample size across max boxes to get number of
        # items to inspect per box.
        else:
            print(
                "Warning: Within box proportion is too low and/or interval is too "
                "high to achieve sample size. Automatically increasing within box "
                "proportion to achieve sample size."
            )
            inspect_per_box = math.ceil(n_items_to_inspect / max_boxes)
            # If not enough boxes to achieve sample size, inspect all items
            # and increase n_boxes_to_inspect as needed.
            if inspect_per_box > items_per_box:
                inspect_per_box = items_per_box
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
    else:
        raise RuntimeError(
            "Unknown cluster selection method: {cluster_selection}".format(**locals())
        )

    # Allow user specified box minimum override calculations
    n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
    assert num_boxes >= n_boxes_to_inspect

    return n_boxes_to_inspect, inspect_per_box


def compute_max_inspectable_items(num_items, items_per_box, within_box_proportion):
    """Compute maximum number of items that can be inspected in a consignment based
    on within box proportion. If within box proportion is less than 1 (partial box
    inspections), then maximum number of items that can be inspected will be
    less than the total number of items in the consignment.

    :param num_items: total number of items in consignment
    :param items_per_box: number of items in each box
    :param within_box_proportion: proportion of items to be inspected per box
    """
    inspect_per_box = math.ceil(within_box_proportion * items_per_box)
    num_full_boxes = math.floor(num_items / items_per_box)
    full_box_inspectable_items = num_full_boxes * inspect_per_box
    remainder_box = num_items % items_per_box
    # Assume that num of items to inspect is based on num of items
    # in full box. Same inspect_per_box will be applied to
    # full and partial boxes.
    remainder_box_inspectable_items = min(remainder_box, inspect_per_box)
    max_items = full_box_inspectable_items + remainder_box_inspectable_items
    return max_items


def select_random_indexes(unit, consignment, n_units_to_inspect):
    """Select units (indexes) from consignment based on sample size and
    random selection strategy.

    :param unit: Unit to be used for inspection (box or item)
    :param consignment: Consignment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined in sample functions.
    """
    if unit in ["item", "items"]:
        indexes_to_inspect = random.sample(
            list(range(consignment.num_items)), n_units_to_inspect
        )
    elif unit in ["box", "boxes"]:
        indexes_to_inspect = random.sample(
            list(range(consignment.num_boxes)), n_units_to_inspect
        )
    else:
        raise RuntimeError("Unknown unit: {unit}".format(**locals()))
    indexes_to_inspect.sort()
    return indexes_to_inspect


def select_cluster_indexes(config, consignment, n_units_to_inspect):
    """Select units (indexes) from consignment based on sample size and
    cluster selection strategy.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined in sample functions.
    """
    unit = config["inspection"]["unit"]
    cluster_selection = config["inspection"]["cluster"]["cluster_selection"]

    if unit in ["item", "items"]:
        if cluster_selection == "random":
            n_boxes_to_inspect = (
                compute_n_clusters_to_inspect(config, consignment, n_units_to_inspect)
            )[0]
            # Choose box indexes randomly
            indexes_to_inspect = random.sample(
                list(range(consignment.num_boxes)), n_boxes_to_inspect
            )
        elif cluster_selection == "interval":
            interval = config["inspection"]["cluster"]["interval"]
            n_boxes_to_inspect = (
                compute_n_clusters_to_inspect(config, consignment, n_units_to_inspect)
            )[0]
            max_boxes = max(1, round(consignment.num_boxes / interval))
            # Check to see if interval is small enough to achieve n_boxes_to_inspect
            # If not, decrease interval.
            if n_boxes_to_inspect > max_boxes:
                interval = round(consignment.num_boxes / n_boxes_to_inspect)
            # Create list of indexes incremented by interval size
            indexes_to_inspect = []
            index = 0
            for unused_i in range(n_boxes_to_inspect):
                indexes_to_inspect.append(index)
                index += interval
        else:
            raise RuntimeError(
                "Unknown cluster selection method: {cluster_unit}".format(**locals())
            )
    elif unit in ["box", "boxes"]:
        raise RuntimeError(
            "Cannot use cluster selection strategy with box sampling unit"
        )
    else:
        raise RuntimeError("Unknown unit: {unit}".format(**locals()))
    indexes_to_inspect.sort()
    return indexes_to_inspect


def select_units_to_inspect(config, consignment, n_units_to_inspect):
    """Select units (indexes) from consignment based on sample size and
    specified selection strategy.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined in sample functions.
    """
    unit = config["inspection"]["unit"]
    selection_strategy = config["inspection"]["selection_strategy"]

    if selection_strategy == "convenience":
        indexes_to_inspect = list(range(n_units_to_inspect))
    elif selection_strategy == "random":
        indexes_to_inspect = select_random_indexes(
            unit, consignment, n_units_to_inspect
        )
    elif selection_strategy == "cluster":
        # Compute number of boxes needed to achieve sample size
        # and select box indexes.
        indexes_to_inspect = select_cluster_indexes(
            config, consignment, n_units_to_inspect
        )
    else:
        raise RuntimeError(
            "Unknown selection strategy: {selection_strategy}".format(**locals())
        )
    return indexes_to_inspect


def inspect(config, consignment, n_units_to_inspect, detailed):
    """Inspect selected units using both end strategies (to detection, to completion)
    Return number of boxes opened, items inspected, and contaminated items found for
    each end strategy.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined by sample functions.
    """
    # Disabling warnings, possible future TODO is splitting this function.
    # pylint: disable=too-many-locals,too-many-statements
    # pylint: disable=too-many-branches,too-many-nested-blocks

    unit = config["inspection"]["unit"]
    selection_strategy = config["inspection"]["selection_strategy"]
    items_per_box = consignment.items_per_box

    indexes_to_inspect = select_units_to_inspect(
        config, consignment, n_units_to_inspect
    )

    # Inspect selected boxes, count opened boxes, inspected items, and contaminated
    # items to detection and completion
    ret = types.SimpleNamespace(
        inspected_item_indexes=[],
        boxes_opened_completion=0,
        boxes_opened_detection=0,
        items_inspected_completion=0,
        items_inspected_detection=0,
        contaminated_items_completion=0,
        contaminated_items_detection=0,
    )

    if unit in ["item", "items"]:
        detected = False
        if selection_strategy == "cluster":
            # Compute num items to inspect per box to achieve sample size
            # based on within box proportion.
            inspect_per_box = (
                compute_n_clusters_to_inspect(config, consignment, n_units_to_inspect)
            )[1]
            ret.boxes_opened_completion = len(indexes_to_inspect)
            items_inspected = 0
            # Loop through selected box indexes (random or interval selection)
            for box_index in indexes_to_inspect:
                if not detected:
                    ret.boxes_opened_detection += 1
                sample_remainder = n_units_to_inspect - items_inspected
                # If sample_remainder is less than inspect_per_box, set inspect_per_box
                # to sample_remainder to avoid inspecting more items than computed
                # sample size.
                if sample_remainder < inspect_per_box:
                    inspect_per_box = sample_remainder
                # In each box, loop through first n items (n = inspect_per_box)
                for item_in_box_index, item in enumerate(
                    (consignment.boxes[box_index]).items[0:inspect_per_box]
                ):
                    if detailed:
                        item_index = consignment.item_in_box_to_item_index(
                            box_index, item_in_box_index
                        )
                        ret.inspected_item_indexes.append(item_index)
                    ret.items_inspected_completion += 1
                    if not detected:
                        ret.items_inspected_detection += 1
                    if item:
                        # Count all contaminated items in sample, regardless of
                        # detected variable
                        ret.contaminated_items_completion += 1
                        if not detected:
                            # Count contaminated items in box if not yet detected
                            ret.contaminated_items_detection += 1
                if ret.contaminated_items_detection > 0:
                    # Update detected variable if contaminated items found in box
                    detected = True
                items_inspected += inspect_per_box
            # assert (
            #     ret.items_inspected_completion == n_units_to_inspect
            # ), """Check if number of items is evenly divisible by items per box.
            # Partial boxes not supported when using cluster selection."""
        else:  # All other item selection strategies inspected the same way
            # Empty lists to hold opened boxes indexes, will be duplicates bc box index
            # computed per inspected item
            boxes_opened_completion = []
            boxes_opened_detection = []
            # Loop through items in sorted index list (sorted in index functions)
            # Inspection progresses through indexes in ascending order
            for item_index in indexes_to_inspect:
                if detailed:
                    ret.inspected_item_indexes.append(item_index)
                ret.items_inspected_completion += 1
                # Compute box index number
                boxes_opened_completion.append(math.floor(item_index / items_per_box))
                if not detected:
                    ret.items_inspected_detection += 1
                    # Compute box index number
                    boxes_opened_detection.append(
                        math.floor(item_index / items_per_box)
                    )
                if consignment.items[item_index]:
                    # Count every contaminated item in sample
                    ret.contaminated_items_completion += 1
                    if not detected:
                        ret.contaminated_items_detection += 1
                        detected = True
                # Should be only 1 contaminated item if to detection
                if detected:
                    assert ret.contaminated_items_detection == 1
            # Number of boxes opened is number of unique boxes indexes in boxes
            # opened lists
            ret.boxes_opened_completion = len(set(boxes_opened_completion))
            ret.boxes_opened_detection = len(set(boxes_opened_detection))
    elif unit in ["box", "boxes"]:
        # Partial box inspections allowed to reduce number of items inspected if desired
        within_box_proportion = config["inspection"]["within_box_proportion"]
        inspect_per_box = int(math.ceil(within_box_proportion * items_per_box))
        detected = False
        ret.boxes_opened_completion = n_units_to_inspect
        ret.items_inspected_completion = n_units_to_inspect * inspect_per_box
        for box_index in indexes_to_inspect:
            if not detected:
                ret.boxes_opened_detection += 1
            # In each box, loop through first n items (n = inspect_per_box)
            for item_in_box_index, item in enumerate(
                (consignment.boxes[box_index]).items[0:inspect_per_box]
            ):
                if detailed:
                    item_index = consignment.item_in_box_to_item_index(
                        box_index, item_in_box_index
                    )
                    ret.inspected_item_indexes.append(item_index)
                if not detected:
                    ret.items_inspected_detection += 1
                if item:
                    # Count every contaminated item in sample
                    ret.contaminated_items_completion += 1
                    # If first contaminated box inspected,
                    # count contaminated items in box
                    if not detected:
                        ret.contaminated_items_detection += 1
            # If box contained contaminated items, changed detected variable
            if ret.contaminated_items_detection > 0:
                detected = True

    ret.consignment_checked_ok = ret.contaminated_items_completion == 0
    return ret


def get_sample_function(config):
    """Based on config, return function to sample a consignment."""
    sample_strategy = config["inspection"]["sample_strategy"]
    if sample_strategy == "proportion":

        def sample(consignment):
            return sample_proportion(config=config, consignment=consignment)

    elif sample_strategy == "hypergeometric":

        def sample(consignment):
            return sample_hypergeometric(config=config, consignment=consignment)

    elif sample_strategy == "fixed_n":

        def sample(consignment):
            return sample_n(config=config, consignment=consignment)

    elif sample_strategy == "all":

        def sample(consignment):
            return sample_all(config=config, consignment=consignment)

    else:
        raise RuntimeError(
            "Unknown sample strategy: {sample_strategy}".format(**locals())
        )
    return sample


def is_flower_of_the_day(cfrp, flower, date):
    """Return True if the flower is FoTD based on naive criteria"""
    i = date.day % len(cfrp)
    if flower == cfrp[i]:
        return True
    return False


def naive_cfrp(config, consignment, date):
    """Decided if the consignment should be expected based on CFRP and size"""
    # returns 2 bools: should_inspect, CFRP applied
    flower = consignment.flower
    cfrp = config["flowers"]
    max_boxes = config["max_boxes"]
    # we have flowers in the CFRP, flower is in CFRP, and not too big consignment
    if cfrp and flower in cfrp and consignment.num_boxes <= max_boxes:
        if is_flower_of_the_day(cfrp, flower, date):
            return True, "naive_cfrp"  # is FotD, inspect
        return False, "naive_cfrp"  # not FotD, release
    return True, None  # not in CFRP or large, inspect


def inspect_always(consignment, date):  # pylint: disable=unused-argument
    """Inspect always"""
    return True, None


def get_inspection_needed_function(config):
    """Based on config, return function to determine is inspection is needed."""
    if "release_programs" in config:
        if "naive_cfrp" in config["release_programs"]:

            def is_inspection_needed(consignment, date):
                return naive_cfrp(
                    config["release_programs"]["naive_cfrp"], consignment, date
                )

        else:
            raise RuntimeError("Unknown release program: {program}".format(**locals()))
    else:
        is_inspection_needed = inspect_always
    return is_inspection_needed


def is_consignment_contaminated(consignment):
    """Return True if at least one box contains contaminants"""
    for box in consignment.boxes:
        if box:
            return True
    return False


def consignment_contamination_rate(consignment):
    """Get (true) contamination rate of a consignment

    Contamination rate is here defined as number of
    contaminated items divided by the number items.
    """
    count = np.count_nonzero(consignment.items)
    return count / consignment.num_items


def count_contaminated_boxes(consignment):
    """Return number of boxes containing contaminants"""
    count = 0
    for box in consignment.boxes:
        if box:
            count += 1
    return count


def count_contaminated_items(consignment):
    """Return number of contaminated items"""
    count = np.count_nonzero(consignment.items)
    return count
