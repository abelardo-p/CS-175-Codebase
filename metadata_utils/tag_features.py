import pandas as pd
import json
import argparse
from preprocess.tokenize_query import tokenize
from metadata_utils.query_complexity import QueryComplexity
from dataclasses import asdict

def jsonl_to_csv(jsonl_path, csv_path):
    rows = []
    with open(jsonl_path, "r") as f:
        for line in f:
            data = json.loads(line)
            sql_features = data.pop("sql_features", {})
            flat_row = {**data, **sql_features}

            rows.append(flat_row)

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)

def main(input_dataset, output_path, convert_to_csv):
    df = pd.read_csv(input_dataset)
    with open(output_path, "w") as f:

        for idx in range(len(df)):

            row = df.iloc[idx]
            db_id = row['db_id']
            question = row['question']
            gold_query = row['query']
            pred_query = row['pred_query']
            
            tokens = tokenize(gold_query)
            qc = QueryComplexity({'query': gold_query, 'query_toks': tokens})
            hardness = qc.get_hardness_level()  

            data = {
                "db_id": db_id,
                "question": question,
                "gold": gold_query,
                "pred": pred_query,
                "tokens": tokens,
                "hardness": hardness,
                "sql_features": asdict(qc.feature_set)
            }

            f.write(json.dumps(data) + "\n")
    
    if convert_to_csv:
        jsonl_to_csv(output_path, output_path)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dataset", type=str, help='Dataset with gold queries', required=True)
    parser.add_argument("--output_path", type=str, help='Output file to contain gold query metadata', required=True)
    parser.add_argument("--convert_to_csv", action="store_true", help="save features to csv file")
    args = parser.parse_args()
    main(args.input_dataset, args.output_path, args.convert_to_csv)
