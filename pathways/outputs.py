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
Various outputs for pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import shutil
import weakref
import csv

from .inspections import count_diseased

if not hasattr(weakref, "finalize"):
    from backports import weakref  # pylint: disable=import-error


def pretty_content(array):
    """Return string with array content nicelly visualized as unicode text

    Values evaluating to False are replaced with a flower, others with a bug.
    """

    def replace(number):
        if number:
            return "\N{Bug}"
        else:
            return "\N{Black Florette}"

    pretty = [replace(i) for i in array]
    return " ".join(pretty)


# Pylint does not see usage of a variables in a format string.
def pretty_header(shipment, line="heavy"):  # pylint: disable=unused-argument
    """Return header for a shipment

    Basic info about the shipment is included and the remainining space
    in a terminal window is filled with horizonal box characters.
    (The assumption is that this will be printed in the terminal.)
    """
    size = 80
    if hasattr(shutil, "get_terminal_size"):
        size = shutil.get_terminal_size().columns
    if line.lower() == "heavy":
        horizontal = "\N{Box Drawings Heavy Horizontal}"
    elif line.lower() == "light":
        horizontal = "\N{Box Drawings Light Horizontal}"
    elif line == "space":
        horizontal = " "
    else:
        horizontal = line
    header = (
        "{horizontal}{horizontal} Shipment"
        " {horizontal}{horizontal}"
        " Boxes: {shipment[num_boxes]} {horizontal}{horizontal}"
        " Stems: {shipment[num_stems]} "
    ).format(**locals())
    if size > len(header):
        size = size - len(header)
    else:
        size = 0
    rule = horizontal * size  # pylint: disable=possibly-unused-variable
    return "{header}{rule}".format(**locals())


def pretty_print_shipment_stems(shipment):
    """Pretty-print shipment focusing on individual stems"""
    print(pretty_header(shipment))
    print(pretty_content(shipment["stems"]))


def pretty_print_shipment_boxes(shipment):
    """Pretty-print shipment showing individual stems in boxes"""
    print(pretty_header(shipment))
    print(" | ".join([pretty_content(box.stems) for box in shipment["boxes"]]))


def pretty_print_shipment_boxes_only(shipment):
    """Pretty-print shipment showing individual boxes"""
    print(pretty_header(shipment, line="light"))
    print(pretty_content(shipment["boxes"]))


def pretty_print_shipment(shipment, style):
    """Pretty-print shipment in a given style

    :param style: Style of pretty-printing (boxes, boxes_only, stems)
    """
    if style == "boxes":
        pretty_print_shipment_boxes(shipment)
    elif style == "boxes_only":
        pretty_print_shipment_boxes_only(shipment)
    elif style == "stems":
        pretty_print_shipment_stems(shipment)
    else:
        raise ValueError(
            "Unknown style value for pretty printing of shipments: {pretty}".format(
                **locals()
            )
        )


class PrintReporter(object):
    """Reporter class which prints a message for each shipment"""

    # Reporter objects carry functions, but many not use any attributes.
    # pylint: disable=no-self-use,missing-function-docstring
    def true_negative(self):
        print("Inspection worked, didn't miss anything (no pest) [TP]")

    def true_positive(self):
        print("Inspection worked, found pest [TN]")

    def false_negative(self, shipment):
        print(
            "Inspection failed, missed {} boxes with pest [FP]".format(
                count_diseased(shipment)
            )
        )


class MuteReporter(object):
    """Reporter class which is completely silent"""

    # pylint: disable=no-self-use,missing-function-docstring
    def true_negative(self):
        pass

    def true_positive(self):
        pass

    def false_negative(self, shipment):
        pass


class Form280(object):
    """Creates F280 records from the simulated data"""

    def __init__(self, file, disposition_codes, separator=","):
        """Prepares file for writing

        :param file: Name of the file to write to or ``-`` (dash) for printing
        :param disposition_codes: Conversion table for output disposition codes
        :param separator: Value (field) separator for the output CSV file
        """
        self.print_to_stdout = False
        self.file = None
        if file:
            if file in ("-", "stdout", "print"):
                self.print_to_stdout = True
            else:
                self.file = open(file, "w")
                self._finalizer = weakref.finalize(self, self.file.close)
        self.codes = disposition_codes
        # selection and order of columns to output
        columns = ["REPORT_DT", "LOCATION", "ORIGIN_NM", "COMMODITY", "disposition"]

        if self.file:
            self.writer = csv.writer(
                self.file,
                delimiter=separator,
                quotechar='"',
                quoting=csv.QUOTE_NONNUMERIC,
            )
            self.writer.writerow(columns)

    def disposition(self, ok, must_inspect, applied_program):
        """Get disposition code for the given parameters

        Provides defaults if the disposition code table does not contain
        a specific value.

        See :meth:`fill` for details about the parameters.
        """
        codes = self.codes
        if applied_program in ["naive_cfrp"]:
            if must_inspect:
                if ok:
                    disposition = codes.get("cfrp_inspected_ok", "OK CFRP Inspected")
                else:
                    disposition = codes.get(
                        "cfrp_inspected_pest", "Pest Found CFRP Inspected"
                    )
            else:
                disposition = codes.get("cfrp_not_inspected", "CFRP Not Inspected")
        else:
            if ok:
                disposition = codes.get("inspected_ok", "OK Inspected")
            else:
                disposition = codes.get("inspected_pest", "Pest Found")
        return disposition

    def fill(self, date, shipment, ok, must_inspect, applied_program):
        """Fill one entry in the F280 form

        :param date: Shipment or inspection date
        :param shipment: Shipment which was tested
        :param ok: True if the shipment was tested negative (no pest present)
        :param must_inspect: True if the shipment was selected for inspection
        :param apllied_program: Identifier of the program applied or None
        """
        disposition_code = self.disposition(ok, must_inspect, applied_program)
        if self.file:
            self.writer.writerow(
                [
                    date.strftime("%Y-%m-%d"),
                    shipment["port"],
                    shipment["origin"],
                    shipment["flower"],
                    disposition_code,
                ]
            )
        elif self.print_to_stdout:
            print(
                "F280: {date:%Y-%m-%d} | {shipment[port]} | {shipment[origin]}"
                " | {shipment[flower]} | {disposition_code}".format(
                    shipment, **locals()
                )
            )


class SuccessRates(object):
    """Record and accumulate success rates"""

    def __init__(self, reporter):
        """Initialize values to zero and set the reporter object"""
        self.ok = 0
        self.true_positive = 0
        self.true_negative = 0
        self.false_negative = 0
        self.reporter = reporter

    def record_success_rate(self, checked_ok, actually_ok, shipment):
        """Record testing result for one shipment

        :param checked_ok: True if the shipment tested negative on presence of pest
        :param checked_ok: True if the shipment actually does not have pest
        :param shipmemt: The shipement itself (for reporting purposes)
        """
        if checked_ok and actually_ok:
            self.true_negative += 1
            self.ok += 1
            self.reporter.true_negative()
        elif not checked_ok and not actually_ok:
            self.true_negative += 1
            self.reporter.true_negative()
        elif checked_ok and not actually_ok:
            self.false_negative += 1
            self.reporter.false_negative(shipment)
        elif not checked_ok and actually_ok:
            raise RuntimeError(
                "Inspection result is infested,"
                " but actually the shipment is not infested (programmer error)"
            )
