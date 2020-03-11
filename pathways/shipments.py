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
import numpy as np
import scipy.stats as stats


class Box:
    """Box or inspection unit

    Evaluates to bool when it contains pest.

    Box is a view into array of stems, i.e. a slice of that array. The
    assumption is that the original, and possibly modifed, stems can be not
    only accessed but also modifed through the box.
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

    # for Python 2 compatibility
    __nonzero__ = __bool__


class ParameterShipmentGenerator:
    """Generate a shipments based on configuration parameters"""

    def __init__(self, parameters, ports, stems_per_box, start_date):
        """Set parameters for shipement generation

        :param parameters: Shipment parameters
        :param ports: List of ports to choose from
        :param stems_per_box: Configuration driving number of stems per box
        :param start_date: Date to start shipment dates from
        """
        self.params = parameters
        self.ports = ports
        self.stems_per_box = stems_per_box
        self.num_generated = 0
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.date = start_date

    def generate_shipment(self):
        """Generate a new shipment"""
        # flowers or commodities
        port = random.choice(self.ports)
        flowers = self.params["flowers"]
        origins = self.params["origins"]
        flower = random.choice(flowers)
        origin = random.choice(origins)
        num_boxes_min = self.params["boxes"].get("min", 0)
        num_boxes_max = self.params["boxes"]["max"]
        stems_per_box = self.stems_per_box["default"]
        num_boxes = random.randint(num_boxes_min, num_boxes_max)
        stems = np.zeros(num_boxes * stems_per_box, dtype=np.int)
        boxes = []
        for i in range(num_boxes):
            lower = i * stems_per_box
            upper = (i + 1) * stems_per_box
            boxes.append(Box(stems[lower:upper]))
        self.num_generated += 1
        # two shipments every nth day
        if self.num_generated % 3:
            self.date += timedelta(days=1)

        return dict(
            flower=flower,
            num_stems=stems_per_box * num_boxes,
            stems=stems,
            num_boxes=num_boxes,
            arrival_time=self.date,
            boxes=boxes,
            origin=origin,
            port=port,
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

        if record["PATHWAY"] == "Airport":
            stems_per_box = self.stems_per_box["air"]["default"]
        elif record["PATHWAY"] == "Maritime":
            stems_per_box = self.stems_per_box["Maritime"]["default"]
        else:
            stems_per_box = self.stems_per_box["default"]

        num_boxes = int(round(num_stems / float(stems_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = []
        for i in range(num_boxes):
            lower = i * stems_per_box
            # slicing does not go over the size even if our last box is smaller
            upper = (i + 1) * stems_per_box
            boxes.append(Box(stems[lower:upper]))

        date = datetime.strptime(record["REPORT_DT"], "%Y-%m-%d")
        return dict(
            flower=record["COMMODITY"],
            num_stems=num_stems,
            stems=stems,
            num_boxes=num_boxes,
            arrival_time=date,
            boxes=boxes,
            origin=record["ORIGIN_NM"],
            port=record["LOCATION"],
        )


def get_shipment_generator(config):
    """Based on config, return shipment generator object."""
    if "input_F280" in config:
        shipment_generator = F280ShipmentGenerator(
            stems_per_box=config["stems_per_box"], filename=config["input_F280"]
        )
    else:
        shipment_generator = ParameterShipmentGenerator(
            parameters=config["shipment"],
            ports=config["ports"],
            stems_per_box=config["stems_per_box"],
            start_date="2020-04-01",
        )
    return shipment_generator


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

    Config is the ``infestation_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "beta":
        param1, param2 = config["parameters"]
        infestation_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(
            "Unknown infestation rate distribution: {distribution}".format(**locals())
        )
    infested_stems = int(num_stems * infestation_rate)
    return infested_stems


def add_pest_uniform_random(config, shipment):
    """Add pests to shipment using uniform random distribution

    Infestation rate is determined using the ``infestation_rate`` config key.
    """
    num_stems = shipment["num_stems"]
    infested_stems = num_stems_to_infest(config["infestation_rate"], num_stems)
    if infested_stems == 0:
        return
    indexes = np.random.choice(num_stems, infested_stems, replace=False)
    np.put(shipment["stems"], indexes, 1)


def add_pest_clusters(config, shipment):
    """Add pest clusters to shipment

    Assuming a list of boxes with the non-infested boxes set to False.

    Each item (box) in boxes (list) is set to True if a pest/pathogen is
    there, False otherwise.
    """
    num_stems = shipment["num_stems"]
    infested_stems = num_stems_to_infest(config["infestation_rate"], num_stems)
    if infested_stems == 0:
        return
    # num_clusters = 1
    cluster_sizes = [infested_stems]
    max_stems_per_cluster = config["clustered"]["max_stems_per_cluster"]
    if infested_stems > max_stems_per_cluster:
        # num_clusters = round(
        #    infested_stems / config["clustered"]["max_stems_per_cluster"]
        # )
        sum_stems = 0
        cluster_sizes = []
        while sum_stems < infested_stems - max_stems_per_cluster:
            sum_stems += max_stems_per_cluster
            cluster_sizes.append(max_stems_per_cluster)
        cluster_sizes.append(infested_stems - sum_stems)
        sum_stems += infested_stems - sum_stems
        assert sum_stems == infested_stems

    for cluster_size in cluster_sizes:
        distribution = config["clustered"]["distribution"]
        if distribution == "gamma":
            param1, param2 = config["clustered"]["parameters"]
            cluster = stats.gamma.rvs(param1, scale=param2, size=cluster_size)
        else:
            raise RuntimeError(
                "Unknown cluster distribution: {distribution}".format(**locals())
            )
        cluster_max = max(cluster)
        if cluster_max > num_stems - 1:
            cluster = np.interp(
                cluster, (cluster.min(), cluster.max()), (0, num_stems - 1)
            )
        else:
            high = num_stems - cluster_max
            cluster_start = np.random.randint(low=0, high=high)
            cluster += cluster_start
        cluster = cluster.astype(np.int)
        # The resulting infestation rate (number of infested stems) might be
        # lower because the clusters overlap.
        np.put(shipment["stems"], cluster, 1)


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
