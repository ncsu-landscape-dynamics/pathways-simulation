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
Consignment and contaminant generation for pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Kellyn P. Montgomery <kellynmontgomery gmail com>
"""

from __future__ import print_function, division

import random
import csv
from datetime import datetime, timedelta
import math
import collections
import numpy as np
import scipy.stats as stats


class Box:
    """Box or inspection unit

    Evaluates to bool when it contains contaminant.

    Box is a view into array of items, i.e. a slice of that array. The
    assumption is that the original, and possibly modifed, items can not
    only be accessed but also modifed through the box.
    """

    def __init__(self, items):
        """Store reference to associated items

        :param items: Array-like object of items
        """
        self.items = items

    @property
    def num_items(self):
        """Number of items in the box"""
        return self.items.shape[0]

    def __bool__(self):
        return bool(np.any(self.items > 0))


class Consignment(collections.UserDict):
    """A consignment with all its properties and what it contains.

    Access is through attributes (new style) or using a dictionary-like item access
    (old style).
    """

    # Inheriting from this library class is its intended use, so disable ancestors msg.
    # pylint: disable=too-many-ancestors
    # This class is meant to hold a lot of attributes.
    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        flower,
        num_items,
        items,
        items_per_box,
        num_boxes,
        date,
        boxes,
        origin,
        port,
        pathway,
    ):
        """Store reference to associated attributes

        :param flower: string
        :param num_items: integer
        :param items_per_box: integer
        :param num_boxes: integer
        :param date: Array-like object of items
        :param boxes: Array-like object of boxes
        :param origin: string
        :param port: string
        :param pathway: string
        """
        super().__init__(
            flower=flower,
            num_items=num_items,
            items=items,
            items_per_box=items_per_box,
            num_boxes=num_boxes,
            date=date,
            boxes=boxes,
            origin=origin,
            port=port,
            pathway=pathway,
        )
        self.flower = flower
        self.num_items = num_items
        self.items = items
        self.items_per_box = items_per_box
        self.num_boxes = num_boxes
        self.date = date
        self.boxes = boxes
        self.origin = origin
        self.port = port
        self.pathway = pathway

    def __getattr__(self, name):
        return self.name

    def count_contaminated(self):
        """Count contaminated items in box."""
        return np.count_nonzero(self.items)

    def item_in_box_to_item_index(self, box_index, item_in_box_index):
        """Convert item index in a box to item index in the consignment"""
        if box_index == 0:
            return item_in_box_index
        items = 0
        for box in self.boxes[:box_index]:
            items += box.num_items
        return items + item_in_box_index


class ParameterConsignmentGenerator:
    """Generate a consignments based on configuration parameters"""

    def __init__(self, parameters, items_per_box, start_date):
        """Set parameters for shipement generation

        :param parameters: Consignment parameters
        :param ports: List of ports to choose from
        :param items_per_box: Configuration driving number of items per box
        :param start_date: Date to start consignment dates from
        """
        self.params = parameters
        self.items_per_box = items_per_box
        self.num_generated = 0
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.date = start_date

    def generate_consignment(self):
        """Generate a new consignment"""
        port = random.choice(self.params["ports"])
        # flowers or commodities
        flower = random.choice(self.params["flowers"])
        origin = random.choice(self.params["origins"])
        num_boxes_min = self.params["boxes"].get("min", 0)
        num_boxes_max = self.params["boxes"]["max"]
        pathway = "None"
        items_per_box = self.items_per_box
        items_per_box = get_items_per_box(items_per_box, pathway)
        num_boxes = random.randint(num_boxes_min, num_boxes_max)
        num_items = items_per_box * num_boxes
        items = np.zeros(num_items, dtype=np.int)
        boxes = []
        for i in range(num_boxes):
            lower = i * items_per_box
            upper = (i + 1) * items_per_box
            boxes.append(Box(items[lower:upper]))
        self.num_generated += 1
        # two consignments every nth day
        if self.num_generated % 3:
            self.date += timedelta(days=1)

        return Consignment(
            flower=flower,
            num_items=num_items,
            items=items,
            items_per_box=items_per_box,
            num_boxes=num_boxes,
            date=self.date,
            boxes=boxes,
            origin=origin,
            port=port,
            pathway=pathway,
        )


class F280ConsignmentGenerator:
    """Generate a consignments based on existing F280 records"""

    def __init__(self, items_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.items_per_box = items_per_box

    def generate_consignment(self):
        """Generate a new consignment"""
        try:
            record = next(self.reader)
        except StopIteration:
            raise RuntimeError(
                "More consignments requested than number of records in provided F280"
            )

        num_items = int(record["QUANTITY"])
        items = np.zeros(num_items, dtype=np.int)

        pathway = record["PATHWAY"]
        items_per_box = self.items_per_box
        items_per_box = get_items_per_box(items_per_box, pathway)

        # rounding up to keep the max per box and have enough boxes
        num_boxes = int(math.ceil(num_items / float(items_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = []
        for i in range(num_boxes):
            lower = i * items_per_box
            # slicing does not go over the size even if our last box is smaller
            upper = (i + 1) * items_per_box
            boxes.append(Box(items[lower:upper]))
        assert sum([box.num_items for box in boxes]) == num_items

        date = datetime.strptime(record["REPORT_DT"], "%Y-%m-%d")
        return Consignment(
            flower=record["COMMODITY"],
            num_items=num_items,
            items=items,
            items_per_box=items_per_box,
            num_boxes=num_boxes,
            date=date,
            boxes=boxes,
            origin=record["ORIGIN_NM"],
            port=record["LOCATION"],
            pathway=pathway,
        )


class AQIMConsignmentGenerator:
    """Generate a consignments based on existing AQIM records"""

    def __init__(self, items_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.items_per_box = items_per_box

    def generate_consignment(self):
        """Generate a new consignment"""
        try:
            record = next(self.reader)
        except StopIteration:
            raise RuntimeError(
                "More consignments requested than number of records in AQIM data"
            )
        pathway = record["CARGO_FORM"]
        items_per_box = self.items_per_box
        items_per_box = get_items_per_box(items_per_box, pathway)
        unit = record["UNIT"]

        # Generate items based on quantity in AQIM records.
        # If quantity is given in boxes, use item_per_box to convert to items.
        if unit in ["Box/Carton"]:
            num_items = int(record["QUANTITY"]) * items_per_box
        elif unit in ["Stems"]:
            num_items = int(record["QUANTITY"])
        else:
            raise RuntimeError("Unsupported quantity unit: {unit}".format(**locals()))

        items = np.zeros(num_items, dtype=np.int)

        # rounding up to keep the max per box and have enough boxes
        num_boxes = int(math.ceil(num_items / float(items_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = []
        for i in range(num_boxes):
            lower = i * items_per_box
            # slicing does not go over the size even if our last box is smaller
            upper = (i + 1) * items_per_box
            boxes.append(Box(items[lower:upper]))
        assert sum([box.num_items for box in boxes]) == num_items

        date = record["CALENDAR_YR"]
        return Consignment(
            flower=record["COMMODITY_LIST"],
            num_items=num_items,
            items=items,
            items_per_box=items_per_box,
            num_boxes=num_boxes,
            date=date,
            boxes=boxes,
            origin=record["ORIGIN"],
            port=record["LOCATION"],
            pathway=pathway,
        )


def get_items_per_box(items_per_box, pathway):
    """Based on config and pathway, return number of items per box."""
    if pathway.lower() == "airport" and "air" in items_per_box:
        items_per_box = items_per_box["air"]["default"]
    elif pathway.lower() == "maritime" and "maritime" in items_per_box:
        items_per_box = items_per_box["maritime"]["default"]
    else:
        items_per_box = items_per_box["default"]
    return items_per_box


def get_consignment_generator(config):
    """Based on config, return consignment generator object."""
    if ("f280_file" in config) and config["f280_file"]:
        consignment_generator = F280ConsignmentGenerator(
            items_per_box=config["consignment"]["items_per_box"],
            filename=config["f280_file"],
        )
    elif ("aqim_file" in config) and config["aqim_file"]:
        consignment_generator = AQIMConsignmentGenerator(
            items_per_box=config["consignment"]["items_per_box"],
            filename=config["aqim_file"],
        )
    else:
        start_date = config["consignment"].get("start_date", "2020-01-01")
        consignment_generator = ParameterConsignmentGenerator(
            parameters=config["consignment"],
            items_per_box=config["consignment"]["items_per_box"],
            start_date=start_date,
        )
    return consignment_generator


# This function is not used or working, consider updating or removing.
def add_contaminant_to_random_box(config, consignment, contamination_rate=None):
    """Add contaminant to consignment

    Assuming a list of boxes with the non-contaminated boxes set to False.

    Each item (box) in boxes (list) is set to True if a contaminant is
    there, False otherwise.

    :param config: ``random_box`` config dictionary
    :param consignment: Consignment to contaminate
    :param contamination_rate: ``contamination_rate`` config dictionary
    """
    contaminant_probability = config["probability"]
    contaminant_ratio = config["ratio"]
    if random.random() >= contaminant_probability:
        return
    for box in consignment.boxes:
        if random.random() < contaminant_ratio:
            in_box = config.get("in_box_arrangement", "all")
            if in_box == "first":
                # simply put one contaminant to first item in the box
                box.items[0] = 1
            elif in_box == "all":
                box.items.fill(1)
            elif in_box == "one_random":
                index = np.random.choice(box.num_items - 1)
                box.items[index] = 1
            elif in_box == "random":
                if not contamination_rate:
                    raise ValueError(
                        "contamination_rate must be set if arrangement is random"
                    )
                num_contaminated_items = num_items_to_contaminate(
                    contamination_rate, box.num_items
                )
                if num_contaminated_items == 0:
                    continue
                indexes = np.random.choice(
                    box.num_items, num_contaminated_items, replace=False
                )
                np.put(box.items, indexes, 1)


def num_items_to_contaminate(config, num_items):
    """Return number of items to be contaminated
    Rounds up or down to nearest integer.

    Config is the ``contamination_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        contamination_rate = config["value"]
    elif distribution == "beta":
        param1, param2 = config["parameters"]
        contamination_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(
            "Unknown contamination rate distribution: {distribution}".format(**locals())
        )
    contaminated_items = round(num_items * contamination_rate)
    return contaminated_items


def num_boxes_to_contaminate(config, num_boxes):
    """Return number of boxes to be contaminated as float.

    Config is the ``contamination_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        contamination_rate = config["value"]
    elif distribution == "beta":
        param1, param2 = config["parameters"]
        contamination_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(
            "Unknown contamination rate distribution: {distribution}".format(**locals())
        )
    contaminated_boxes = num_boxes * contamination_rate
    return contaminated_boxes


def add_contaminant_uniform_random(config, consignment):
    """Add contaminants to consignment using uniform random distribution

    Contamination rate is determined using the ``contamination_rate`` config key.
    """
    contamination_unit = config["contamination_unit"]
    if contamination_unit in ["box", "boxes"]:
        contaminated_boxes = num_boxes_to_contaminate(
            config["contamination_rate"], consignment.num_boxes
        )
        if contaminated_boxes == 0.0:
            return
        box_indexes = np.random.choice(
            consignment.num_boxes, math.ceil(contaminated_boxes), replace=False
        )
        # Contaminate full boxes except for last one
        for box_index in box_indexes[:-1]:
            consignment.boxes[box_index].items.fill(1)
        # Use remainder of contaminated_boxes to partially contaminate
        # last box if needed
        partial_box_proportion = math.modf(contaminated_boxes)[0]
        # If contaminated_boxes is whole number, contaminate full box
        if partial_box_proportion == 0.0:
            partial_box_proportion = 1
        partial_box_contaminated_stems = round(
            consignment.boxes[box_indexes[-1]].num_items * partial_box_proportion
        )
        consignment.boxes[box_indexes[-1]].items[0:partial_box_contaminated_stems].fill(
            1
        )
        # Check if correct number of boxes contaminated, should be rounded up
        # contaminated_boxes, or may be rounded down contaminated_boxes
        # if no stems were contaminated in last partial box
        assert np.count_nonzero(consignment.boxes) in (
            math.ceil(contaminated_boxes),
            math.floor(contaminated_boxes),
        )
    elif contamination_unit in ["item", "items"]:
        contaminated_items = num_items_to_contaminate(
            config["contamination_rate"], consignment.num_items
        )
        if contaminated_items == 0:
            return
        item_indexes = np.random.choice(
            consignment.num_items, contaminated_items, replace=False
        )
        np.put(consignment.items, item_indexes, 1)
        assert np.count_nonzero(consignment.items) == contaminated_items
    else:
        raise RuntimeError(
            "Unknown contamination unit: {contamination_unit}".format(**locals())
        )


def _contaminated_items_to_cluster_sizes(
    contaminated_items, contaminated_units_per_cluster
):
    """Get list of cluster sizes for a given number of contaminated items

    The size of each cluster is limited by contaminated_units_per_cluster.
    """
    if contaminated_items > contaminated_units_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining items.
        # Alternative would be sth like:
        # round(contaminated_items/contaminated_units_per_cluster)
        sum_items = 0
        cluster_sizes = []
        while sum_items < contaminated_items - contaminated_units_per_cluster:
            sum_items += contaminated_units_per_cluster
            cluster_sizes.append(contaminated_units_per_cluster)
        # add remaining items
        cluster_sizes.append(contaminated_items - sum_items)
        sum_items += contaminated_items - sum_items
        assert sum_items == contaminated_items
    else:
        cluster_sizes = [contaminated_items]
    return cluster_sizes


def _contaminated_boxes_to_cluster_sizes(
    contaminated_boxes, contaminated_units_per_cluster
):
    """Get list of cluster sizes for a given number of contaminated items

    The size of each cluster is limited by contaminated_units_per_cluster.
    """
    contaminated_boxes = math.ceil(contaminated_boxes)
    if contaminated_boxes > contaminated_units_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining items.
        sum_boxes = 0
        cluster_sizes = []
        while sum_boxes < contaminated_boxes - contaminated_units_per_cluster:
            sum_boxes += contaminated_units_per_cluster
            cluster_sizes.append(contaminated_units_per_cluster)
        # add last cluster with remaining contaminated boxes
        cluster_sizes.append(contaminated_boxes - sum_boxes)
        sum_boxes += contaminated_boxes - sum_boxes
        assert sum_boxes == contaminated_boxes
    else:
        cluster_sizes = [math.ceil(contaminated_boxes)]
    return cluster_sizes


def choose_strata_for_clusters(num_units, cluster_width, num_clusters):
    """Divide array of items or boxes into strata wide enough for clusters
    so that they do not overlap. If array is not equally divisible by cluster_width,
    create one smaller strata that can be used for a smaller cluster if needed.
    This is important for very high contamination rates that require nearly all units
    to be contaminated.
    Randomly select strata to place contaminant clusters. If contamination rate is
    low enough that not all strata are needed, omit smaller strata created from
    remainder and only select from strata wide enough to contain full sized cluster.
    Return strata selected to contaminate with clusters.

    num_units: number of boxes or items in consignment
    cluster_width: size of cluster in terms of boxes or units
    num_clusters: number of clusters to contaminate
    """
    # Round up so that one smaller remainder stratum is included
    num_strata = max(1, math.ceil(num_units / cluster_width))
    # Make sure there are enough strata for the number of clusters needed.
    if num_strata < num_clusters:
        raise ValueError(
            """Cannot avoid overlapping clusters. Increase contaminated_units_per_cluster
            or decrease cluster_item_width (if using item contamination_unit)"""
        )
    # If all strata are needed, all strata are selected for clusters
    if num_clusters == num_strata:
        cluster_strata = np.arange(num_strata)
    # If not all strata needed (num of clusters is less than num of strata), do not use
    # last strata if its smaller than cluster_width (remainder from rounding up)
    else:
        # if no remainder (all strata are equal length), select any strata for clusters
        if num_units % cluster_width == 0:
            cluster_strata = np.random.choice(num_strata, num_clusters, replace=False)
        # if last strata is smaller and not all strata are needed,
        # do not include last strata as option for placing clusters
        else:
            cluster_strata = np.random.choice(
                num_strata - 1, num_clusters, replace=False
            )
    return cluster_strata


def add_contaminant_clusters_to_boxes(config, consignment):
    """Add contaminant clusters to boxes in a consignment"""
    contaminated_units_per_cluster = config["clustered"][
        "contaminated_units_per_cluster"
    ]
    num_boxes = consignment.num_boxes
    contaminated_boxes = num_boxes_to_contaminate(
        config["contamination_rate"], num_boxes
    )
    if contaminated_boxes == 0:
        return
    cluster_sizes = _contaminated_boxes_to_cluster_sizes(
        contaminated_boxes, contaminated_units_per_cluster
    )
    cluster_strata = choose_strata_for_clusters(
        num_boxes, contaminated_units_per_cluster, len(cluster_sizes)
    )
    # Contaminate full boxes in all clusters except the last one
    for index, cluster_size in enumerate(cluster_sizes[:-1]):
        # Find starting index of strata (cluster width * strata index)
        cluster_start = contaminated_units_per_cluster * cluster_strata[index]
        cluster_indexes = np.arange(
            start=cluster_start, stop=cluster_start + cluster_size
        )
        for cluster_index in cluster_indexes:
            consignment.boxes[cluster_index].items.fill(1)
    # In last box of last cluster, contaminate partial box if needed
    cluster_start = (
        contaminated_units_per_cluster * cluster_strata[len(cluster_sizes) - 1]
    )
    cluster_indexes = np.arange(
        start=cluster_start, stop=cluster_start + cluster_sizes[-1]
    )
    for cluster_index in cluster_indexes[:-1]:
        consignment.boxes[cluster_index].items.fill(1)
    # Use remainder of contaminated_boxes to partially contaminate last box
    partial_box_proportion = math.modf(contaminated_boxes)[0]
    # If contaminated_boxes is whole number, contaminate full box
    if partial_box_proportion == 0.0:
        partial_box_proportion = 1
    partial_box_contaminated_stems = round(
        consignment.boxes[cluster_indexes[-1]].num_items * partial_box_proportion
    )
    consignment.boxes[cluster_indexes[-1]].items[0:partial_box_contaminated_stems].fill(
        1
    )
    # Check if correct number of boxes contaminated, should be rounded up
    # contaminated_boxes, or may be rounded down contaminated_boxes
    # if no stems were contaminated in last partial box
    assert np.count_nonzero(consignment.boxes) in (
        math.ceil(contaminated_boxes),
        math.ceil(contaminated_boxes) - 1,
    )


def add_contaminant_clusters_to_items(config, consignment):
    """Add contaminant clusters to items in a consignment"""
    contaminated_units_per_cluster = config["clustered"][
        "contaminated_units_per_cluster"
    ]
    num_items = consignment.num_items
    contaminated_items = num_items_to_contaminate(
        config["contamination_rate"], num_items
    )
    if contaminated_items == 0:
        return
    cluster_sizes = _contaminated_items_to_cluster_sizes(
        contaminated_items, contaminated_units_per_cluster
    )
    cluster_indexes = []
    distribution = config["clustered"]["distribution"]
    if distribution == "random":
        cluster_item_width = config["clustered"]["random"]["cluster_item_width"]
        if cluster_item_width < contaminated_units_per_cluster:
            raise ValueError(
                "Maximum cluster width, currently {cluster_item_width}, needs"
                " to be at least as large as contaminated_units_per_cluster"
                " (currently {contaminated_units_per_cluster})".format(**locals())
            )
        # cluster can't be wider/longer than the current list of items
        cluster_item_width = min(cluster_item_width, num_items)
        cluster_strata = choose_strata_for_clusters(
            num_items, cluster_item_width, len(cluster_sizes)
        )
        for index, cluster_size in enumerate(cluster_sizes):
            cluster_start = cluster_item_width * cluster_strata[index]
            # Use smaller cluster width if placing items in smaller remainder stratum
            cluster_width = min(
                cluster_item_width, (consignment.num_items - cluster_start)
            )
            assert (
                cluster_width >= cluster_size
            ), "Not enough items available to contaminate in selected cluster stratum."
            cluster = np.random.choice(cluster_width, cluster_size, replace=False)
            cluster += cluster_start
            cluster_indexes.extend(list(cluster))
    elif distribution == "continuous":
        cluster_strata = choose_strata_for_clusters(
            num_items, contaminated_units_per_cluster, len(cluster_sizes)
        )
        for index, cluster_size in enumerate(cluster_sizes):
            cluster = np.arange(cluster_size)
            cluster_start = contaminated_units_per_cluster * cluster_strata[index]
            cluster += cluster_start
            cluster_indexes.extend(list(cluster))
    else:
        raise RuntimeError(
            "Unknown cluster distribution: {distribution}".format(**locals())
        )
    cluster_indexes = np.array(cluster_indexes, dtype=np.int)
    assert min(cluster_indexes) >= 0, "Cluster values need to be valid indices"
    assert max(cluster_indexes) < num_items
    np.put(consignment.items, cluster_indexes, 1)
    assert np.count_nonzero(consignment.items) == contaminated_items


def add_contaminant_clusters(config, consignment):
    """Add contaminant clusters to consignment

    Item (separately or in boxes) with contaminat in *consignment* evaluate
    to True after runing this function.
    This function does not touch the not items not selected for contamination.
    However, they are expected to be zero.
    """
    contamination_unit = config["contamination_unit"]
    if contamination_unit in ["box", "boxes"]:
        add_contaminant_clusters_to_boxes(config, consignment)
    elif contamination_unit in ["item", "items"]:
        add_contaminant_clusters_to_items(config, consignment)
    else:
        raise RuntimeError(
            "Unknown contamination unit: {contamination_unit}".format(**locals())
        )


def get_contaminant_function(config):
    """Get function for adding contaminant to a consignment based on configuration"""
    arrangement = config["contamination"]["arrangement"]
    if arrangement == "random_box":

        def add_contaminant_function(consignment):
            return add_contaminant_to_random_box(
                config=config["contamination"]["random_box"],
                consignment=consignment,
                contamination_rate=config["contamination"]["contamination_rate"],
            )

    elif arrangement == "random":

        def add_contaminant_function(consignment):
            return add_contaminant_uniform_random(
                config=config["contamination"], consignment=consignment
            )

    elif arrangement == "clustered":

        def add_contaminant_function(consignment):
            return add_contaminant_clusters(
                config=config["contamination"], consignment=consignment
            )

    else:
        raise RuntimeError(
            "Unknown contaminant arrangement: {arrangement}".format(**locals())
        )
    return add_contaminant_function
