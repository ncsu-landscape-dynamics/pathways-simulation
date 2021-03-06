from pathways.scenarios import run_scenarios, load_scenario_table
from pathways.simulation import load_configuration
from pathways.outputs import save_scenario_result_to_table


def main():
    basic_config = load_configuration("tests/test_scenarios/config.yml")
    scenario_table = load_scenario_table(
        "tests/test_scenarios/scenarios_config_subset.csv"
    )
    results = run_scenarios(
        config=basic_config,
        scenario_table=scenario_table,
        seed=42,
        num_simulations=1,
        num_consignments=1000,
    )
    assert len(scenario_table) == len(results)
    save_scenario_result_to_table(
        "results.csv",
        results,
        config_columns=[
            "name",
            "consignment/boxes/min",
            "consignment/boxes/max",
            "consignment/items_per_box/default",
            "contamination/contamination_rate/parameters",
            "contamination/arrangement",
            "inspection/unit",
            "inspection/sample_strategy",
            "inspection/proportion/value",
            "inspection/hypergeometric/detection_level",
            "inspection/selection_strategy",
            "inspection/within_box_proportion",
            "inspection/cluster/cluster_selection",
        ],
        result_columns=[
            "missing",
            "true_contamination_rate",
            "max_missed_contamination_rate",
            "avg_missed_contamination_rate",
            "max_intercepted_contamination_rate",
            "avg_intercepted_contamination_rate",
            "avg_boxes_opened_completion",
            "avg_boxes_opened_detection",
            "avg_items_inspected_completion",
            "avg_items_inspected_detection",
            "pct_sample_if_to_detection",
            "pct_contaminants_unreported_if_detection",
            "total_missed_contaminants",
            "total_intercepted_contaminants",
            "false_neg",
            "intercepted",
        ],
    )


if __name__ == "__main__":
    main()
