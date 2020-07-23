#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Simulation for evaluataion of pathways
# Copyright (C) 2018-2020 Vaclav Petras

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
Inspections of shipments in pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import math
import random
import types
import weakref
import numpy as np

from .shipments import get_stems_per_box

if not hasattr(weakref, "finalize"):
    from backports import weakref  # pylint: disable=import-error


def inspect_first(shipment):
    """Inspect only the first box in the shipment"""
    if shipment["boxes"][0]:
        return False, 1
    return True, 1


def inspect_one_random(shipment):
    """Inspect only one randomly picked box in the shipment"""
    if random.choice(shipment["boxes"]):
        return False, 1
    return True, 1


def inspect_all(shipment):
    """Inspect all boxes in the shipment"""
    return not is_shipment_diseased(shipment), shipment["num_boxes"]


def inspect_first_n(num_boxes, shipment):
    """Inspect only the first n boxes in the shipment

    :param num_boxes: Number of boxes to inspect
    :param shipment: Shipment to inspect
    """
    num_boxes = min(len(shipment["boxes"]), num_boxes)
    for i in range(num_boxes):
        if shipment["boxes"][i]:
            return False, i + 1
    return True, num_boxes


def sample_percentage(config, shipment):
    """Set sample size to sample units from shipment using percentage strategy.
    Return number of units to inspect.

    :param config: Configuration to be used595
    :param shipment: Shipment to be inspected
    """
    unit = config["inspection"]["unit"]
    ratio = config["inspection"]["percentage"]["proportion"]
    num_stems = shipment["num_stems"]
    num_boxes = shipment["num_boxes"]
    min_boxes = config.get("min_boxes", 1)

    if unit in ["stem", "stems"]:
        n_units_to_inspect = int(math.ceil(ratio * num_stems))
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = int(math.ceil(ratio * num_boxes))
        n_units_to_inspect = max(min_boxes, n_units_to_inspect)
        n_units_to_inspect = min(num_boxes, n_units_to_inspect)
    else:
        raise RuntimeError("Unknown sampling unit: {unit}".format(**locals()))
    return n_units_to_inspect


def compute_hypergeometric(population_size, detection_level, confidence_level):
    """Get sample size using hypergeometric distribution

    Compute sample size using hypergeometric distribution based on population
    size (total number of stems or boxes in shipment), detection level,
    and confidence level.
    """
    sample_size = math.ceil(
        (1 - ((1 - confidence_level) ** (1 / (detection_level * population_size))))
        * (population_size - (((detection_level * population_size) - 1) / 2))
    )
    return sample_size


def sample_hypergeometric(config, shipment):
    """Set sample size to sample units from shipment using hypergeometric/detection
    level strategy. Return number of units to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    unit = config["inspection"]["unit"]
    detection_level = config["inspection"]["hypergeometric"]["detection_level"]
    confidence_level = config["inspection"]["hypergeometric"]["confidence_level"]
    num_stems = shipment["num_stems"]
    num_boxes = shipment["num_boxes"]
    min_boxes = config.get("min_boxes", 1)

    if unit in ["stem", "stems"]:
        n_units_to_inspect = compute_hypergeometric(
            num_stems, detection_level, confidence_level
        )
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = compute_hypergeometric(
            num_boxes, detection_level, confidence_level
        )
        n_units_to_inspect = max(min_boxes, n_units_to_inspect)
        n_units_to_inspect = min(num_boxes, n_units_to_inspect)
    else:
        raise RuntimeError("Unknown sampling unit: {unit}".format(**locals()))
    return n_units_to_inspect


def sample_all(config, shipment):
    """Set sample size to sample all units from shipment.
    Return number of units to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    unit = config["inspection"]["unit"]
    if unit in ["stem", "stems"]:
        n_units_to_inspect = shipment["num_stems"]
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = shipment["num_boxes"]
    return n_units_to_inspect


def sample_n(config, shipment):
    """Set sample size to sample fixed number of units from shipment.
    Check if fixed number is <= max units for inspection.
    Return number of units to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    fixed_n = config["inspection"]["fixed_n"]
    unit = config["inspection"]["unit"]
    within_box_pct = config["inspection"]["within_box_pct"]
    pathway = shipment["pathway"]
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, pathway)
    num_stems = shipment["num_stems"]
    num_boxes = shipment["num_boxes"]
    min_boxes = config.get("min_boxes", 1)

    if unit in ["stem", "stems"]:
        max_stems = compute_max_inspectable_stems(
            num_stems, stems_per_box, within_box_pct
        )
        # Check if max number of stems that can be inspected is less than fixed number.
        n_units_to_inspect = min(max_stems, fixed_n)
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = fixed_n
        n_units_to_inspect = max(min_boxes, n_units_to_inspect)
        n_units_to_inspect = min(num_boxes, n_units_to_inspect)
    return n_units_to_inspect


def convert_stems_to_boxes_fixed_pct(config, shipment, n_stems_to_inspect):
    """Convert number of stems to inspect to number of boxes to inspect based on
    the number of stems per box and the percentage of stems to inspect per box
    specified in the config. Adjust number of boxes to inspect to be at least
    the minimum number specified in the config and total number of boxes in shipment.
    Return number of boxes to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    :param n_stems_to_inspect: Number of stems to inspect defined in sample functions.
    """
    pathway = shipment["pathway"]
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, pathway)
    within_box_pct = config["inspection"]["within_box_pct"]
    min_boxes = config.get("min_boxes", 1)
    num_boxes = shipment["num_boxes"]
    inspect_per_box = int(math.ceil(within_box_pct * stems_per_box))

    # Default inspect all stems per box, but allow partial box inspections
    n_boxes_to_inspect = math.ceil(n_stems_to_inspect / inspect_per_box)
    n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
    n_boxes_to_inspect = min(num_boxes, n_boxes_to_inspect)
    return n_boxes_to_inspect


def compute_n_outer_to_inspect(config, shipment, n_stems_to_inspect):
    """Compute number of outer units (boxes) that need to be opened to achieve stem
    sample size when using the hierarchical selection strategy. Use config within box
    percent if possible or compute minimum number of stems to inspect per box
    required to achieve stem sample size.
    Return number of boxes to inspect and number of stems to inspect per box.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    :param n_stems_to_inspect: Number of stems to inspect defined by sample functions.
    """
    outer = config["inspection"]["hierarchical"]["outer"]
    pathway = shipment.pathway
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, pathway)
    within_box_pct = config["inspection"]["within_box_pct"]
    min_boxes = config.get("min_boxes", 1)
    num_boxes = shipment.num_boxes
    num_stems = shipment.num_stems

    if outer == "random":
        max_stems = compute_max_inspectable_stems(
            num_stems, stems_per_box, within_box_pct
        )
        if max_stems >= n_stems_to_inspect:
            inspect_per_box = math.ceil(within_box_pct * stems_per_box)
            n_boxes_to_inspect = math.ceil(n_stems_to_inspect / inspect_per_box)
        else:
            inspect_per_box = math.ceil(n_stems_to_inspect / num_boxes)
            n_boxes_to_inspect = math.ceil(n_stems_to_inspect / inspect_per_box)

    elif outer == "interval":
        interval = config["inspection"]["hierarchical"]["interval"]
        max_boxes = max(1, round(num_boxes / interval))
        max_stems = max_boxes * (math.ceil(within_box_pct * stems_per_box))
        if max_stems >= n_stems_to_inspect:
            inspect_per_box = math.ceil(within_box_pct * stems_per_box)
            n_boxes_to_inspect = math.ceil(n_stems_to_inspect / inspect_per_box)
        else:
            inspect_per_box = math.ceil(n_stems_to_inspect / max_boxes)
            n_boxes_to_inspect = math.ceil(n_stems_to_inspect / inspect_per_box)
    else:
        raise RuntimeError("Unknown outer unit: {outer}".format(**locals()))

    n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
    assert num_boxes >= n_boxes_to_inspect

    return n_boxes_to_inspect, inspect_per_box


def compute_max_inspectable_stems(num_stems, stems_per_box, within_box_pct):
    """Compute maximum number of stems that can be inspected in a shipment based
    on within box percent. If within box percent is less than 1 (partial box
    inspections), then maximum number of stems that can be inspected will be
    less than the total number of stems in the shipment.

    :param num_stems: total number of stems in shipment
    :param stems_per_box: number of stems in each box
    :param within_box_pct: percentage of stems to be inspected per box
    """
    inspect_per_box = math.ceil(within_box_pct * stems_per_box)
    num_full_boxes = math.floor(num_stems / stems_per_box)
    full_box_inspectable_stems = num_full_boxes * inspect_per_box
    remainder_box = num_stems % stems_per_box
    remainder_box_inspectable_stems = min(remainder_box, inspect_per_box)
    max_stems = full_box_inspectable_stems + remainder_box_inspectable_stems
    return max_stems


def select_units_to_inspect(config, shipment, n_units_to_inspect):
    """Select units (indexes) from shipment based on sample size and
    specified selection strategy.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined in sample functions.
    """
    unit = config["inspection"]["unit"]
    selection_strategy = config["inspection"]["selection_strategy"]
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, shipment.pathway)

    if selection_strategy == "tailgate":
        indexes_to_inspect = range(n_units_to_inspect)
    elif selection_strategy == "random":
        if unit in ["stem", "stems"]:
            indexes_to_inspect = random.sample(
                range(shipment.num_stems), n_units_to_inspect
            )
        elif unit in ["box", "boxes"]:
            indexes_to_inspect = random.sample(
                range(shipment.num_boxes), n_units_to_inspect
            )
        else:
            raise RuntimeError("Unknown unit: {unit}".format(**locals()))
    elif selection_strategy == "hierarchical":
        outer = config["inspection"]["hierarchical"]["outer"]
        if unit in ["stem", "stems"]:
            if outer == "random":
                n_boxes_to_inspect = (
                    compute_n_outer_to_inspect(config, shipment, n_units_to_inspect)
                )[0]
                indexes_to_inspect = random.sample(
                    range(shipment.num_boxes), n_boxes_to_inspect
                )
            elif outer == "interval":
                interval = config["inspection"]["hierarchical"]["interval"]
                n_boxes_to_inspect = (
                    compute_n_outer_to_inspect(config, shipment, n_units_to_inspect)
                )[0]
                indexes_to_inspect = []
                index = 0
                for unused_i in range(n_boxes_to_inspect):
                    indexes_to_inspect.append(index)
                    index += interval
            else:
                raise RuntimeError("Unknown outer unit: {outer}".format(**locals()))
        elif unit in ["box", "boxes"]:
            raise RuntimeError(
                "Cannot use hierarchical selection strategy with box sampling unit"
            )
        else:
            raise RuntimeError("Unknown unit: {unit}".format(**locals()))
    else:
        raise RuntimeError(
            "Unknown selection strategy: {selection_strategy}".format(**locals())
        )
    return indexes_to_inspect


def inspect(config, shipment, n_units_to_inspect):
    """Inspect selected units using both end strategies (to detection, to completion)
    Return number of boxes opened, stems inspected, and infested stems found for
    each end strategy.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined by sample functions.
    """
    # Disabling warnings, possible future TODO is splitting this function.
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements

    unit = config["inspection"]["unit"]
    selection_strategy = config["inspection"]["selection_strategy"]
    pathway = shipment["pathway"]
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, pathway)

    indexes_to_inspect = select_units_to_inspect(config, shipment, n_units_to_inspect)

    # Inspect selected boxes, count opened boxes, inspected stems, and infested stems
    # to detection and completion
    ret = types.SimpleNamespace(
        boxes_opened_completion=0,
        boxes_opened_detection=0,
        stems_inspected_completion=0,
        stems_inspected_detection=0,
        infested_stems_completion=0,
        infested_stems_detection=0,
    )

    if unit in ["stem", "stems"]:
        detected = False
        ret.stems_inspected_completion = n_units_to_inspect
        if selection_strategy == "hierarchical":
            inspect_per_box = (
                compute_n_outer_to_inspect(config, shipment, n_units_to_inspect)
            )[1]
            ret.boxes_opened_completion = len(indexes_to_inspect)
            for box in indexes_to_inspect:
                if not detected:
                    ret.boxes_opened_detection += 1
                for stem in (shipment.boxes[box]).stems[0:inspect_per_box]:
                    if not detected:
                        ret.stems_inspected_detection += 1
                    if stem:  # Count infested stems in partial box sample to completion
                        ret.infested_stems_completion += 1
                        if not detected:
                            ret.infested_stems_detection += 1
                if ret.infested_stems_detection > 0:
                    detected = True
        else:
            boxes_opened_completion = []
            boxes_opened_detection = []
            for stem in indexes_to_inspect:
                boxes_opened_completion.append(
                    math.ceil(stem / stems_per_box)
                )  # Compute box index number
                if not detected:
                    ret.stems_inspected_detection += 1
                    boxes_opened_detection.append(
                        math.ceil(stem / stems_per_box)
                    )  # Compute box index number
                if shipment.stems[stem]:  # Count every infested stem in sample
                    ret.infested_stems_completion += 1
                    if not detected:
                        ret.infested_stems_detection += 1
                        detected = True
            ret.boxes_opened_completion = len(set(boxes_opened_completion))
            ret.boxes_opened_detection = len(set(boxes_opened_detection))
    elif unit in ["box", "boxes"]:
        within_box_pct = config["inspection"][
            "within_box_pct"
        ]  # If less than 1.0, portion of stems in each box will be inspected tailgate
        inspect_per_box = int(
            math.ceil(within_box_pct * stems_per_box)
        )  # This may be very similar to hierarchical - if so, partial box
        # inspections functionality for box sample unit could be removed.
        detected = False
        ret.boxes_opened_completion = n_units_to_inspect
        ret.stems_inspected_completion = n_units_to_inspect * inspect_per_box
        for box in indexes_to_inspect:
            if not detected:
                ret.boxes_opened_detection += 1
            for stem in (shipment.boxes[box]).stems[0:inspect_per_box]:
                if not detected:
                    ret.stems_inspected_detection += 1
                if stem:  # Count every infested stem in box, to completion within a box
                    ret.infested_stems_completion += 1
                    if not detected:
                        ret.infested_stems_detection += 1
            if ret.infested_stems_detection > 0:
                detected = True

    ret.shipment_checked_ok = ret.infested_stems_completion == 0
    return ret


def get_sample_function(config):
    """Based on config, return function to sample a shipment.
    """
    sample_strategy = config["inspection"]["sample_strategy"]
    if sample_strategy == "percentage":

        def sample(shipment):
            return sample_percentage(config=config, shipment=shipment)

    elif sample_strategy == "hypergeometric":

        def sample(shipment):
            return sample_hypergeometric(config=config, shipment=shipment)

    elif sample_strategy == "fixed_n":

        def sample(shipment):
            return sample_n(config=config, shipment=shipment)

    elif sample_strategy == "all":

        def sample(shipment):
            return sample_all(config=config, shipment=shipment)

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


def naive_cfrp(config, shipment, date):
    """Decided if the shipment should be expected based on CFRP and size"""
    # returns 2 bools: should_inspect, CFRP applied
    flower = shipment["flower"]
    cfrp = config["flowers"]
    max_boxes = config["max_boxes"]
    # we have flowers in the CFRP, flower is in CFRP, and not too big shipment
    if cfrp and flower in cfrp and shipment["num_boxes"] <= max_boxes:
        if is_flower_of_the_day(cfrp, flower, date):
            return True, "naive_cfrp"  # is FotD, inspect
        return False, "naive_cfrp"  # not FotD, release
    return True, None  # not in CFRP or large, inspect


def inspect_always(shipment, date):  # pylint: disable=unused-argument
    """Inspect always"""
    return True, None


def get_inspection_needed_function(config):
    """Based on config, return function to determine is inspection is needed."""
    if "release_programs" in config:
        if "naive_cfrp" in config["release_programs"]:

            def is_inspection_needed(shipment, date):
                return naive_cfrp(
                    config["release_programs"]["naive_cfrp"], shipment, date
                )

        else:
            raise RuntimeError("Unknown release program: {program}".format(**locals()))
    else:
        is_inspection_needed = inspect_always
    return is_inspection_needed


def is_shipment_diseased(shipment):
    """Return True if at least one box has pest"""
    for box in shipment["boxes"]:
        if box:
            return True
    return False


def shipment_infestation_rate(shipment):
    """Get (true) infestation rate of a shipment

    Infestation rate is here defined as number of
    infested stems divided by the number stems.
    """
    count = np.count_nonzero(shipment["stems"])
    return count / shipment["num_stems"]


def count_diseased_boxes(shipment):
    """Return number of boxes with pest"""
    count = 0
    for box in shipment["boxes"]:
        if box:
            count += 1
    return count


def count_diseased_stems(shipment):
    """Return number of stems with pest"""
    count = np.count_nonzero(shipment["stems"])
    return count
