import argparse
import os
from metadata_utils import tag_features, link_schema_features
from evaluation.execution_evaluate import (
    evaluate_execution, convert_dataset_to_dicts, output_results_to_csv
)
from deserialize_db_model import deserialize_db_schema_model
from metadata_utils.fetch_schema_features import analyze_directory
from evaluation.plot.plot_exec_accuracies import plot as plot_exec
from evaluation.plot.plot_partial_accuracies import plot as plot_partial
from evaluation.structural_evaluate import evaluate_dataset
from evaluation.average_partial_accuracies import aggregate_results_by_clause


def handle_execution_accuracy(args):
    samples = convert_dataset_to_dicts(args.input_dataset)
    accuracy, results = evaluate_execution(samples, args.db_dir, args.engine, True if args.log_resultsets else False)
    print(f"Accuracy: {accuracy}")
    try:
        os.makedirs(args.output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error creating directory '{args.output_dir}': {e}")

    exec_results_file = os.path.join(args.output_dir, "exec_evaluation_results.csv")
    metadata_file = os.path.join(args.output_dir, "dataset_with_metadata.csv")
    schema_stats_file = os.path.join(args.output_dir, "schema_stats.json")
    output_results_to_csv(exec_results_file, results)
    tag_features.main(args.input_dataset, metadata_file, True)
    analyze_directory(args.db_dir, schema_stats_file)
    link_schema_features.main(schema_stats_file, metadata_file, metadata_file)
    plot_exec(accuracy, args.output_dir, metadata_file, exec_results_file)


def handle_partial_component_accuracy(args):
    try:
        os.makedirs(args.output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error creating directory '{args.output_dir}': {e}")
    schemas = deserialize_db_schema_model('data/spider/interim_db_schemas_object')
    scores_out_file = os.path.join(args.output_dir, 'partial_scores.csv')
    parsing_errors_log_file = os.path.join(args.output_dir, 'parse_errors.csv')
    all_scores = evaluate_dataset(args.input_dataset, scores_out_file, parsing_errors_log_file, schemas)
    aggregate_scores = aggregate_results_by_clause(all_scores)
    plot_partial(*aggregate_scores, args.output_dir)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--eval_type", type=str, 
                        help="execution or component-based matching", required=True)
    parser.add_argument("--input_dataset", type=str, 
                        help="Dataset with gold and pred queries", required=True)
    parser.add_argument("--output_dir", type=str, 
                        help="Directory to output evaluation results and other interim files", required=True)
    parser.add_argument("--db_dir", type=str, 
                        help="Directory containing either sqlite database files or postgres credentials to db", required=True)
    parser.add_argument("--engine", type=str,
                        help="Indicates whether to use sqlite or postgres", required=False)
    parser.add_argument("--log_resultsets", action="store_true", help="Logs result sets", required=False)

    args = parser.parse_args()
    if args.eval_type == 'exec':
        handle_execution_accuracy(args)
    elif args.eval_type == 'component':
        handle_partial_component_accuracy(args)
    else:
        raise Exception("Invalid evaluation type specified!")
