import pandas as pd

"""Performs a stratified evaluation of the execution accuracy results over the extracted metadata"""
def generate_stratified_accuracies(metadata_csv, accuracies_csv):

    accuracies = {}
    # Input Dataset with NLQ, gold, pred, and query/schema features
    df_features = pd.read_csv(metadata_csv)

    # Dataset with execution results
    df_exec = pd.read_csv(accuracies_csv)
    df_exec = df_exec.drop('db_id', axis=1)

    df = pd.concat([df_features, df_exec], axis=1)
    df["exec_accuracy"] = df["correct"].astype(int)

    # Average acc over Hardness Level (of gold query)
    hardness_order = ["easy", "medium", "hard", "extra"]
    df['hardness'] = pd.Categorical(df['hardness'], categories=hardness_order, ordered=True)
    accuracies['acc_by_hardness'] = df.groupby("hardness")["exec_accuracy"].mean()

    # Average acc over Number of Joins
    accuracies['acc_by_joins'] = df.groupby("num_joins")["exec_accuracy"].mean()

    # Average acc over Number of Aggregations
    accuracies['acc_by_aggs'] = df.groupby("num_agg")["exec_accuracy"].mean()

    # Average acc over Number of Where conditions
    accuracies['acc_by_where'] = df.groupby("num_where_conditions")["exec_accuracy"].mean()

    # Average acc over Subquery status 
    df['has_subquery'] = df['has_subquery'].astype(int)
    accuracies['acc_by_subqquery'] = df.groupby('has_subquery')['exec_accuracy'].mean()

    # Average acc over different query length (in tokens) bins
    df["query_length_bin"] = pd.cut(df["query_length"], bins=[0,10,20,50,100])
    accuracies['acc_by_query_length'] = df.groupby('query_length_bin')['exec_accuracy'].mean()

    # Average acc over different number of tables
    df["num_tables_bin"] = pd.cut(df["num_tables"], bins=[0,1,2,3,4,5,10,15])
    accuracies['acc_by_num_tables'] = df.groupby("num_tables_bin")["exec_accuracy"].mean()

    # Average acc over different count of total columns in schema
    df["num_columns_bin"] = pd.cut(df["num_columns"], bins=[0, 5, 10, 20, 50, 100])
    accuracies['acc_by_total_schema_cols'] = df.groupby("num_columns_bin")["exec_accuracy"].mean()

    # Average acc over number of foreign keys in schema
    accuracies['acc_by_num_fkeys'] = df.groupby("num_foreign_keys")["exec_accuracy"].mean()
    return accuracies, df


if __name__ == '__main__':
    accuracies, df = generate_stratified_accuracies("data/spider/test_with_metadata.csv", "execution_eval_results.csv")