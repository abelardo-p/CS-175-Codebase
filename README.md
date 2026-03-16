## entrypoint.py
This script runs one of two types of evaluation pipelines on a dataset of gold and predicted SQL queries:

1. **Execution-based accuracy (`exec`)**  
   Compares the actual query results against the given database to compute execution accuracy and performs a stratified evaluation based on schema and gold query features.

2. **Structural-based accuracy (`component`)**  
   Evaluates the predicted queries by comparing SQL components (SELECT, WHERE, JOIN, etc.) against the gold queries.

*Note: The input dataset must contain the fields named as :* 
- **(question)** for the NL-question, 
- **(query)** for the gold query, 
- **(pred query)** for the model's query prediction.

An example is given by 'combined.csv'.
You can specify a directory (`output_dir`) to store all contents created by running the script.

## Usage:

```bash
python entrypoint.py \
    --eval_type <exec|component> \
    --input_dataset <path_to_dataset.csv> \
    --output_dir <output_directory> \
    --db_dir <database_directory_or_postgres_credentials> \
    [--engine <sqlite|postgres>] \ # only for exec
    [--log_resultsets]  # optional, only for exec
```

## Arguments

- `--eval_type`: Type of evaluation (exec or component)
- `--input_dataset`: CSV file containing gold and predicted queries
- `--output_dir`: Directory to save evaluation results, plots, and metadata
- `--db_dir`: Directory containing SQLite databases or PostgreSQL credentials
- `--engine`: (optional) Choose 'sqlite' or postgres (needed if not SQLite)
- `--log_resultsets`: (optional) Optional flag to log query result sets (only for execution-based evaluation)

The script will generate CSV results, metadata, schema statistics, and visualizations in the output directory. Examples are shown by folders 'testing_dir' (for exec) and 'testing_dir_2' (for component-based). The last two arguments are only needed for exec-based evaluation.

## Tag Gold Queries with Metadata

If you want to only label the gold queries in your dataset with metadata (tokens, query hardness, SQL features), you can run the `tag_features.py` script by itself:

```bash
python tag_features.py \
    --input_dataset <path_to_dataset.csv> \
    --output_path <output_file.jsonl_or_csv> \
    [--convert_to_csv]  # optional, saves output as CSV instead of JSONL
```

- `--input_dataset`: CSV file containing gold queries
- `--output_path`: File to save the annotated dataset
- `--convert_to_csv`: Optional flag to save output as CSV (default is JSONL)

This will generate a file where each row includes the gold query, its tokens, query hardness (check hardness.txt for a detailed breakdown), and other SQL features. You can also use `query_complexity.py` to extract metadata for a single query string. 

## Execution Accuracy (itself)
If you alternatively want to just run the execution accuracy on your dataset without a stratified analysis, you can run `execution_evaluate.py` as is:

```python
python execution_evaluate.py \
    --input_dataset <path_to_dataset.csv> \
    --db_dir <database_directory_or_postgres_credentials> \
    --engine <sqlite|postgres> \
    --output_path <output_file.csv> \
    [--log_resultsets]  # optional, logs the query result sets
```

- `--input_dataset`: CSV file containing gold and predicted queries
- `--db_dir`: Directory containing SQLite databases or PostgreSQL credentials
- `--engine`: Choose sqlite or postgres
- `--output_path`: CSV file to save per-example execution results
- `--log_resultsets`: Optional flag to log the actual query result sets

This will generate a CSV with execution accuracy for each example in the dataset.

## Scoring two queries (gold & pred) by structural similarity:

The file `canonical_query_representation.txt` defines the core building blocks used to break down the SQL clauses, as well as the format of a parsed SQL representation. Then `structural_evaluate.py` is used to get the F1, precision, and recall scores across all clauses between two queries, generating a scores dict. You can use the file `parse_pair.py` to generate the score breakdown by running the `score_pair()` function with the gold and pred queries as input.
