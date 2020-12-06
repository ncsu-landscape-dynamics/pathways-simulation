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
Shipment and pest generation for pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
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

    Evaluates to bool when it contains pest.

    Box is a view into array of stems, i.e. a slice of that array. The
    assumption is that the original, and possibly modifed, stems can not
    only be accessed but also modifed through the box.
    """

    def __init__(self, stems):
        """Store reference to associated stems

        :param stems: Array-like object of stems
        """
        self.stems = stems

    @property
    def num_stems(self):
        """Number of stems in the box"""
        return self.stems.shape[0]

    def __bool__(self):
        return bool(np.any(self.stems > 0))


class Shipment(collections.UserDict):
    """A shipment with all its properties and what it contains.

    Access is through attributes (new style) or using a dictionary-like item access
    (old style).
    """

    # Inheriting from this library class is its intended use, so disable ancestors msg.
    # pylint: disable=too-many-ancestors

    def __getattr__(self, name):
        return self[name]

    def count_infested(self):
        """Count infested stems in box."""
        return np.count_nonzero(self.stems)


class ParameterShipmentGenerator:
    """Generate a shipments based on configuration parameters"""

    def __init__(self, parameters, stems_per_box, start_date):
        """Set parameters for shipement generation

        :param parameters: Shipment parameters
        :param ports: List of ports to choose from
        :param stems_per_box: Configuration driving number of stems per box
        :param start_date: Date to start shipment dates from
        """
        self.params = parameters
        self.stems_per_box = stems_per_box
        self.num_generated = 0
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.date = start_date

    def generate_shipment(self):
        """Generate a new shipment"""
        port = random.choice(self.params["ports"])
        # flowers or commodities
        flower = random.choice(self.params["flowers"])
        origin = random.choice(self.params["origins"])
        num_boxes_min = self.params["boxes"].get("min", 0)
        num_boxes_max = self.params["boxes"]["max"]
        pathway = "None"
        stems_per_box = self.stems_per_box
        stems_per_box = get_stems_per_box(stems_per_box, pathway)
        num_boxes = random.randint(num_boxes_min, num_boxes_max)
        num_stems = stems_per_box * num_boxes
        stems = np.zeros(num_stems, dtype=np.int)
        boxes = []
        for i in range(num_boxes):
            lower = i * stems_per_box
            upper = (i + 1) * stems_per_box
            boxes.append(Box(stems[lower:upper]))
        self.num_generated += 1
        # two shipments every nth day
        if self.num_generated % 3:
            self.date += timedelta(days=1)

        return Shipment(
            flower=flower,
            num_stems=num_stems,
            stems=stems,
            stems_per_box=stems_per_box,
            num_boxes=num_boxes,
            arrival_time=self.date,
            boxes=boxes,
            origin=origin,
            port=port,
            pathway=pathway,
        )


class F280ShipmentGenerator:
    """Generate a shipments based on existing F280 records"""

    def __init__(self, stems_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.stems_per_box = stems_per_box

    def generate_shipment(self):
        """Generate a new shipment"""
        try:
            record = next(self.reader)
        except StopIteration:
            raise RuntimeError(
                "More shipments requested than number of records in provided F280"
            )

        num_stems = int(record["QUANTITY"])
        stems = np.zeros(num_stems, dtype=np.int)

        pathway = record["PATHWAY"]
        stems_per_box = self.stems_per_box
        stems_per_box = get_stems_per_box(stems_per_box, pathway)

        # rounding up to keep the max per box and have enough boxes
        num_boxes = int(math.ceil(num_stems / float(stems_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = []
        for i in range(num_boxes):
            lower = i * stems_per_box
            # slicing does not go over the size even if our last box is smaller
            upper = (i + 1) * stems_per_box
            boxes.append(Box(stems[lower:upper]))
        assert sum([box.num_stems for box in boxes]) == num_stems

        date = datetime.strptime(record["REPORT_DT"], "%Y-%m-%d")
        return Shipment(
            flower=record["COMMODITY"],
            num_stems=num_stems,
            stems=stems,
            stems_per_box=stems_per_box,
            num_boxes=num_boxes,
            arrival_time=date,
            boxes=boxes,
            origin=record["ORIGIN_NM"],
            port=record["LOCATION"],
            pathway=pathway,
        )


class AQIMShipmentGenerator:
    """Generate a shipments based on existing AQIM records"""

    def __init__(self, stems_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.stems_per_box = stems_per_box

    def generate_shipment(self):
        """Generate a new shipment"""
        try:
            record = next(self.reader)
        except StopIteration:
            raise RuntimeError(
                "More shipments requested than number of records in provided AQIM data"
            )
        pathway = record["CARGO_FORM"]
        stems_per_box = self.stems_per_box
        stems_per_box = get_stems_per_box(stems_per_box, pathway)
        unit = record["UNIT"]

        # Generate stems based on quantity in AQIM records.
        # If quantity is given in boxes, use stem_per_box to convert to stems.
        if unit in ["Box/Carton"]:
            num_stems = int(record["QUANTITY"]) * stems_per_box
        elif unit in ["Stems"]:
            num_stems = int(record["QUANTITY"])
        else:
            raise RuntimeError("Unsupported quantity unit: {unit}".format(**locals()))

        stems = np.zeros(num_stems, dtype=np.int)

        # rounding up to keep the max per box and have enough boxes
        num_boxes = int(math.ceil(num_stems / float(stems_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = []
        for i in range(num_boxes):
            lower = i * stems_per_box
            # slicing does not go over the size even if our last box is smaller
            upper = (i + 1) * stems_per_box
            boxes.append(Box(stems[lower:upper]))
        assert sum([box.num_stems for box in boxes]) == num_stems

        date = record["CALENDAR_YR"]
        return Shipment(
            flower=record["COMMODITY_LIST"],
            num_stems=num_stems,
            stems=stems,
            stems_per_box=stems_per_box,
            num_boxes=num_boxes,
            arrival_time=date,
            boxes=boxes,
            origin=record["ORIGIN"],
            port=record["LOCATION"],
            pathway=pathway,
        )


def get_stems_per_box(stems_per_box, pathway):
    """Based on config and pathway, return number of stems per box."""
    if pathway.lower() == "airport" and "air" in stems_per_box:
        stems_per_box = stems_per_box["air"]["default"]
    elif pathway.lower() == "maritime" and "maritime" in stems_per_box:
        stems_per_box = stems_per_box["maritime"]["default"]
    else:
        stems_per_box = stems_per_box["default"]
    return stems_per_box


def get_shipment_generator(config):
    """Based on config, return shipment generator object."""
    if "f280_file" in config:
        shipment_generator = F280ShipmentGenerator(
            stems_per_box=config["shipment"]["stems_per_box"],
            filename=config["f280_file"],
        )
    elif "aqim_file" in config:
        shipment_generator = AQIMShipmentGenerator(
            stems_per_box=config["shipment"]["stems_per_box"],
            filename=config["aqim_file"],
        )
    else:
        start_date = config["shipment"].get("start_date", "2020-01-01")
        shipment_generator = ParameterShipmentGenerator(
            parameters=config["shipment"],
            stems_per_box=config["shipment"]["stems_per_box"],
            start_date=start_date,
        )
    return shipment_generator


# This function is not used or working, consider updating or removing.
def add_pest_to_random_box(config, shipment, infestation_rate=None):
    """Add pest to shipment

    Assuming a list of boxes with the non-infested boxes set to False.

    Each item (box) in boxes (list) is set to True if a pest/pathogen is
    there, False otherwise.

    :param config: ``random_box`` config dictionary
    :param shipment: Shipment to infest
    :param infestation_rate: ``infestation_rate`` config dictionary
    """
    pest_probability = config["probability"]
    pest_ratio = config["ratio"]
    if random.random() >= pest_probability:
        return
    for box in shipment["boxes"]:
        if random.random() < pest_ratio:
            in_box = config.get("in_box_arrangement", "all")
            if in_box == "first":
                # simply put one pest to first stem in the box
                box.stems[0] = 1
            elif in_box == "all":
                box.stems.fill(1)
            elif in_box == "one_random":
                index = np.random.choice(box.num_stems - 1)
                box.stems[index] = 1
            elif in_box == "random":
                if not infestation_rate:
                    raise ValueError(
                        "infestation_rate must be set if arrangement is random"
                    )
                num_infested_stems = num_stems_to_infest(
                    infestation_rate, box.num_stems
                )
                if num_infested_stems == 0:
                    continue
                indexes = np.random.choice(
                    box.num_stems, num_infested_stems, replace=False
                )
                np.put(box.stems, indexes, 1)


def num_stems_to_infest(config, num_stems):
    """Return number of stems to be infested
    Rounds up or down to nearest integer.

    Config is the ``infestation_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        infestation_rate = config["value"]
    elif distribution == "beta":
        param1, param2 = config["parameters"]
        infestation_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(
            "Unknown infestation rate distribution: {distribution}".format(**locals())
        )
    infested_stems = round(num_stems * infestation_rate)
    return infested_stems


def num_boxes_to_infest(config, num_boxes):
    """Return number of boxes to be infested.
    Rounds up or down to nearest integer.

    Config is the ``infestation_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        infestation_rate = config["value"]
    elif distribution == "beta":
        param1, param2 = config["parameters"]
        infestation_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(
            "Unknown infestation rate distribution: {distribution}".format(**locals())
        )
    infested_boxes = round(num_boxes * infestation_rate)
    return infested_boxes


def add_pest_uniform_random(config, shipment):
    """Add pests to shipment using uniform random distribution

    Infestation rate is determined using the ``infestation_rate`` config key.
    """
    infestation_unit = config["infestation_unit"]
    if infestation_unit in ["box", "boxes"]:
        infested_boxes = num_boxes_to_infest(
            config["infestation_rate"], shipment.num_boxes
        )
        if infested_boxes == 0:
            return
        indexes = np.random.choice(shipment.num_boxes, infested_boxes, replace=False)
        for index in indexes:
            shipment.boxes[index].stems.fill(1)
        assert np.count_nonzero(shipment["boxes"]) == infested_boxes
    if infestation_unit in ["stem", "stems"]:
        infested_stems = num_stems_to_infest(
            config["infestation_rate"], shipment.num_stems
        )
        if infested_stems == 0:
            return
        indexes = np.random.choice(shipment.num_stems, infested_stems, replace=False)
        np.put(shipment["stems"], indexes, 1)
        assert np.count_nonzero(shipment["stems"]) == infested_stems


def _infested_stems_to_cluster_sizes(infested_stems, max_infested_stems_per_cluster):
    """Get list of cluster sizes for a given number of infested stems

    The size of each cluster is limited by max_infested_stems_per_cluster.
    """
    if infested_stems > max_infested_stems_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining stems.
        # Alternative would be sth like round(infested_stems/max_infested_stems_per_cluster)
        sum_stems = 0
        cluster_sizes = []
        while sum_stems < infested_stems - max_infested_stems_per_cluster:
            sum_stems += max_infested_stems_per_cluster
            cluster_sizes.append(max_infested_stems_per_cluster)
        # add remaining stems
        cluster_sizes.append(infested_stems - sum_stems)
        sum_stems += infested_stems - sum_stems
        assert sum_stems == infested_stems
    else:
        cluster_sizes = [infested_stems]
    return cluster_sizes


def _infested_boxes_to_cluster_sizes(infested_boxes, max_boxes_per_cluster):
    """Get list of cluster sizes for a given number of infested stems

    The size of each cluster is limited by max_infested_stems_per_cluster.
    """
    if infested_boxes > max_boxes_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining stems.
        sum_boxes = 0
        cluster_sizes = []
        while sum_boxes < infested_boxes - max_boxes_per_cluster:
            sum_boxes += max_boxes_per_cluster
            cluster_sizes.append(max_boxes_per_cluster)
        # add remaining boxes
        cluster_sizes.append(infested_boxes - sum_boxes)
        sum_boxes += infested_boxes - sum_boxes
        assert sum_boxes == infested_boxes
    else:
        cluster_sizes = [infested_boxes]
    return cluster_sizes


def add_pest_clusters(config, shipment):
    """Add pest clusters to shipment

    Assuming a list of boxes with the non-infested boxes set to False.

    Each item (box) in boxes (list) is set to True if a pest/pathogen is
    there, False otherwise.
    """
    infestation_unit = config["infestation_unit"]
    max_infested_stems_per_cluster = config["clustered"][
        "max_infested_stems_per_cluster"
    ]

    if infestation_unit in ["box", "boxes"]:
        num_boxes = shipment.num_boxes
        infested_boxes = num_boxes_to_infest(config["infestation_rate"], num_boxes)
        if infested_boxes == 0:
            return
        max_boxes_per_cluster = math.ceil(
            max_infested_stems_per_cluster / shipment["stems_per_box"]
        )
        cluster_sizes = _infested_boxes_to_cluster_sizes(
            infested_boxes, max_boxes_per_cluster
        )
        strata = max(1, math.floor(shipment.num_boxes / max_boxes_per_cluster))
        cluster_strata = np.random.choice(strata, len(cluster_sizes), replace=False)
        for index, cluster_size in enumerate(cluster_sizes):
            cluster_start = (
                math.floor(shipment.num_boxes / strata) * cluster_strata[index]
            )
            cluster_indexes = np.arange(
                start=cluster_start, stop=cluster_start + cluster_size
            )
            for cluster_index in cluster_indexes:
                shipment.boxes[cluster_index].stems.fill(1)
        assert np.count_nonzero(shipment["boxes"]) <= infested_boxes

    elif infestation_unit in ["stem", "stems"]:
        num_stems = shipment.num_stems
        infested_stems = num_stems_to_infest(config["infestation_rate"], num_stems)
        if infested_stems == 0:
            return
        cluster_sizes = _infested_stems_to_cluster_sizes(
            infested_stems, max_infested_stems_per_cluster
        )
        cluster_indexes = []
        distribution = config["clustered"]["distribution"]
        if distribution == "gamma":
            param1, param2 = config["clustered"]["parameters"]
            gamma_min_max = stats.gamma.interval(0.999, param1, scale=param2)
            max_width = gamma_min_max[1] - gamma_min_max[0]
            if max_width < max_infested_stems_per_cluster:
                raise ValueError(
                    "Gamma distribution width (currently {max_width},"
                    " determined by shape and rate parameters)"
                    " needs to be at least as large as max_infested_stems_per_cluster"
                    " (currently {max_infested_stems_per_cluster})".format(**locals())
                )
            # cluster can't be wider/longer than the current list of stems
            max_width = min(max_width, num_stems)
            strata = max(1, math.floor(num_stems / max_width))
            cluster_strata = np.random.choice(strata, len(cluster_sizes), replace=False)
            for index, cluster_size in enumerate(cluster_sizes):
                cluster = stats.gamma.rvs(param1, scale=param2, size=cluster_size)
                cluster_start = math.floor((num_stems / strata) * cluster_strata[index])
                cluster += cluster_start
                cluster_indexes.extend(list(cluster))
        elif distribution == "random":
            max_width = config["clustered"]["parameters"][0]
            if max_width < max_infested_stems_per_cluster:
                raise ValueError(
                    "First parameter of random distribution (maximum cluster width,"
                    " currently {max_width})"
                    " needs to be at least as large as max_infested_stems_per_cluster"
                    " (currently {max_infested_stems_per_cluster})".format(**locals())
                )
            # cluster can't be wider/longer than the current list of stems
            max_width = min(max_width, num_stems)
            strata = max(1, math.floor(num_stems / max_width))
            cluster_strata = np.random.choice(strata, len(cluster_sizes), replace=False)
            for index, cluster_size in enumerate(cluster_sizes):
                cluster = np.random.choice(max_width, cluster_size, replace=False)
                cluster_start = math.floor((num_stems / strata) * cluster_strata[index])
                cluster += cluster_start
                cluster_indexes.extend(list(cluster))
        elif distribution == "continuous":
            strata = max(
                1, math.floor(shipment.num_boxes / max_infested_stems_per_cluster)
            )
            cluster_strata = np.random.choice(strata, len(cluster_sizes), replace=False)
            for index, cluster_size in enumerate(cluster_sizes):
                cluster = np.arange(0, cluster_size)
                cluster_start = math.floor((num_stems / strata) * cluster_strata[index])
                cluster += cluster_start
                cluster_indexes.extend(list(cluster))
        else:
            raise RuntimeError(
                "Unknown cluster distribution: {distribution}".format(**locals())
            )
        cluster_indexes = np.array(cluster_indexes, dtype=np.int)
        assert min(cluster_indexes) >= 0, "Cluster values need to be valid indices"
        cluster_max = max(cluster_indexes)
        if cluster_max > num_stems - 1:
            # If the max index specified by the cluster is outside of stem
            # array index range, fit the cluster values into that range.
            cluster_indexes = np.interp(
                cluster_indexes,
                (cluster_indexes.min(), cluster_indexes.max()),
                (0, num_stems - 1),
            )
        assert (
            max(cluster_indexes) < num_stems
        ), "Cluster values need to be valid indices"
        np.put(shipment["stems"], cluster_indexes, 1)
        # if len(np.unique(cluster_indexes)) == cluster_size
        assert np.count_nonzero(shipment["stems"]) <= infested_stems

    else:
        raise RuntimeError(
            "Unknown infestation unit: {infestation_unit}".format(**locals())
        )


def get_pest_function(config):
    """Get function for adding pest to a shipment based on configuration"""
    arrangement = config["pest"]["arrangement"]
    if arrangement == "random_box":

        def add_pest_function(shipment):
            return add_pest_to_random_box(
                config=config["pest"]["random_box"],
                shipment=shipment,
                infestation_rate=config["pest"]["infestation_rate"],
            )

    elif arrangement == "random":

        def add_pest_function(shipment):
            return add_pest_uniform_random(config=config["pest"], shipment=shipment)

    elif arrangement == "clustered":

        def add_pest_function(shipment):
            return add_pest_clusters(config=config["pest"], shipment=shipment)

    else:
        raise RuntimeError("Unknown pest arrangement: {arrangement}".format(**locals()))
    return add_pest_function
