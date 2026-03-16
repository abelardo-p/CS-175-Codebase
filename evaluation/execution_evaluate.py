import sqlite3
import pandas as pd
import psycopg2
import numpy as np
import argparse

execution_errors = ['Syntax Error', 'Missing Table', 'Missing Column', 'Ambiguous Column', 'Datatype Mismatch', 'Other Error']

"""***Assumes sqlite or postgres"""
def execute_query(db_path, query, engine):
    """Execute SQL query and return results (or error)."""
    try:
        if engine == 'sqlite':
            conn = sqlite3.connect(db_path)
        else:
            host, port, dbname, user, password = db_path
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password
            )
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

def categorize_error(error_msg):
    """Map raw SQLite error messages into helpful categories."""
    if error_msg is None:
        return None
    msg = error_msg.lower()
    if "syntax error" in msg:
        return "Syntax Error"
    if "no such table" in msg:
        return "Missing Table"
    if "no such column" in msg:
        return "Missing Column"
    if "ambiguous column" in msg:
        return "Ambiguous Column"
    if "datatype mismatch" in msg:
        return "Datatype Mismatch"
    return "Other Error"


def match_result_sets(gold_df, pred_df, order_sensitive=False):
    """Compare two DataFrames ignoring column order, enforcing row order only if needed."""
    if gold_df.shape != pred_df.shape:
        return False

    gold_cols = list(gold_df.columns)

    used_pred = set()
    for gcol in gold_cols:
        gseries = gold_df[gcol]
        matched = False
        for pcol in pred_df.columns:
            if pcol in used_pred:
                continue
            pseries = pred_df[pcol]

            if order_sensitive:
                # row-by-row match
                if gseries.equals(pseries):
                    used_pred.add(pcol)
                    matched = True
                    break
            else:
                # compare as multisets (ignore row order)
                if set(gseries) == set(pseries) and gseries.value_counts().equals(pseries.value_counts()):
                    used_pred.add(pcol)
                    matched = True
                    break
        if not matched:
            return False

    return True

def evaluate_execution(samples, db_dir, engine: str, log_resultsets: bool):
    """
    samples: list of dicts like
        {"db_id": "database_name", "gold": "SELECT ...", "pred": "SELECT ..."}
    """
    results = []
    correct_count = 0

    for s in samples:
        db_path = f"{db_dir}/{s['db_id']}/{s['db_id']}.sqlite"

        gold_query, pred_query = s["gold"], s["pred"]
        gold_df, gold_err = execute_query(db_path, gold_query, engine)
        pred_df, pred_err = execute_query(db_path, pred_query, engine)

        gold_cat = categorize_error(gold_err)
        pred_cat = categorize_error(pred_err)

        correct = False
        order_sensitive = "order by" in gold_query.lower()
        if gold_err is None and pred_err is None:
            correct = match_result_sets(gold_df, pred_df, order_sensitive)

        result = {
            "db_id": s["db_id"],
            "correct": correct,
            "gold_error": gold_cat,
            "pred_error": pred_cat
        }

        if log_resultsets:
            result["gold_rs"] = gold_df.values.tolist() if gold_df is not None else None
            result["pred_rs"] = pred_df.values.tolist() if pred_df is not None else None

        results.append(result)
        if correct:
            correct_count += 1

    accuracy = correct_count / len(samples)
    return accuracy, results

def convert_dataset_to_dicts(dataset_path : str):
    df = pd.read_csv(dataset_path)
    results = []
    for i in range(len(df)):
        sample = df.iloc[i]
        queries = {"db_id": sample['db_id'],
                   "gold": sample['query'],
                   "pred": sample['pred_query']
                   }
        results.append(queries)
    return results

def output_results_to_csv(output_path: str, results: list[dict]):
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)

def main(args):
    samples = convert_dataset_to_dicts(args.input_dataset)
    # Format of samples
    # samples = [
    #     {
    #         "db_id": "concert_singer",
    #         "gold": "SELECT song_name ,  song_release_year FROM singer ORDER BY age LIMIT 1",
    #         "pred": "SELECT T2.name, T2.country, T2.age FROM singer AS T1 INNER JOIN concert AS T2 ON T1.singer_id = T2.singer_id ORDER BY T2.age DESC"
    #     },
    #     {
    #         "db_id": "college_1",
    #         "gold": "SELECT STU_LNAME AS l_name, STU_FNAME FROM student WHERE PROF_NUM > 300 ORDER BY STU_LNAME DESC",
    #         "pred": "SELECT STU_FNAME, STU_LNAME FROM student WHERE PROF_NUM > 300 ORDER BY STU_LNAME DESC"
    #     }
    # ]
    accuracy, results = evaluate_execution(samples, args.db_dir, args.engine, args.log_resultsets)
    print(accuracy)
    output_results_to_csv(args.output_path, results)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dataset", type=str, 
                        help="Dataset with gold and pred queries", required=True)
    parser.add_argument("--db_dir", type=str, 
                        help="Directory containing either sqlite database files or postgres credentials to db", required=True)
    parser.add_argument("--engine", type=str,
                        help="Indicates whether to use sqlite or postgres", required=True)
    parser.add_argument("--output_path", type=str, 
                        help="Output file for accuracy results per example", required=True)
    parser.add_argument("--log_resultsets", action="store_true", 
                        help="Logs result sets")
    args = parser.parse_args()
    main(args)
    