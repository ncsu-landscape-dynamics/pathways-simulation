import pytest
from pathways.simulation import run_simulation, load_configuration_yaml_from_text


CONFIG = """\
consignment:
  origins:
  - Netherlands
  - Mexico
  flowers:
  - Hyacinthus
  - Rosa
  - Gerbera
  ports:
  - NY JFK CBP
  - FL Miami Air CBP
  boxes:
    min: 1
    max: 50
  items_per_box:
    default: 10
contamination:
  contamination_unit: items
  contamination_rate:
    distribution: beta
    parameters:
    - 4
    - 60
  arrangement: random_box
  random_box:
    probability: 0.2
    ratio: 0.5
inspection:
  unit: boxes
  within_box_proportion: 1
  sample_strategy: proportion
  tolerance_level: 0
  min_boxes: 0
  proportion:
    value: 0.02
  hypergeometric:
    detection_level: 0.05
    confidence_level: 0.95
  fixed_n: 10
  selection_strategy: random
  cluster:
    cluster_selection: random
    interval: 3
"""


def test_simulation_runs():
    """Check that the simulation runs

    This should contain parameters which at one point failed the simulation.
    """
    for seed in range(10):
        run_simulation(
            config=load_configuration_yaml_from_text(CONFIG),
            num_simulations=1,
            num_consignments=10,
            seed=seed,
        )


@pytest.mark.parametrize("num_simulations", [1, 2, 3, 15])
def test_gives_reasonable_result(num_simulations):
    """Check that the result from the simualtion is in the expected range"""
    num_consignments = 100
    # We modify the existing configuration rather than defining a completely
    # new one as a separate YAML.
    min_boxes = 30
    max_boxes = 150
    config = load_configuration_yaml_from_text(CONFIG)
    config["consignment"]["boxes"]["min"] = min_boxes
    config["consignment"]["boxes"]["max"] = max_boxes
    for seed in range(10):
        result = run_simulation(
            config=config, num_simulations=1, num_consignments=100, seed=seed
        )
        test_min_boxes = min_boxes * num_consignments
        test_max_boxes = max_boxes * num_consignments
        assert test_min_boxes <= result.num_boxes <= test_max_boxes
        assert 0 <= result.pct_boxes_opened_completion <= 100
        assert 0 <= result.pct_boxes_opened_detection <= 100
        assert 0 <= result.pct_items_inspected_completion <= 100
        assert 0 <= result.pct_items_inspected_detection <= 100
        assert 0 <= result.pct_contaminant_unreported_if_detection <= 100
