import sys
import subprocess


CONFIG = """\
consignment:
  boxes:
    min: 1
    max: 50
  items_per_box:
    default: 10
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
  sample_strategy: hypergeometric
  min_boxes: 0
  tolerance_level: 0
  proportion:
    value: 0.02
  hypergeometric:
    detection_level: 0.1
    confidence_level: 0.95
  fixed_n: 10
  selection_strategy: random
  cluster:
    cluster_selection: random
    interval: 3
"""


def key_to_option(key):
    return "--{}".format(key.replace("_", "-"))


def dict_to_options(dictionary):
    options = []
    for key, value in dictionary.items():
        options.append(key_to_option(key))
        options.append("{}".format(value))
    return options


def run_pathways_cli(**kwargs):
    # Using unpacking into a list literal from Python 3.5
    return subprocess.check_output(
        [sys.executable, "-m", "pathways", *dict_to_options(kwargs)],
        universal_newlines=True,
    )


def test_gives_result(tmp_path):
    config = tmp_path / "config.yml"
    config.write_text(CONFIG)
    for seed in range(10):
        assert "slipped" in run_pathways_cli(
            num_consignments=10, config_file=str(config), seed=seed
        )
