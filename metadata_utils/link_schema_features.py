import json
import pandas as pd

"""Adds fields to each sample/row in the given dataset csv for schema details"""

def main(schema_stats_file, input_file, output_file):
     with open(schema_stats_file, 'r') as file:
        schema_stats = json.load(file)
        df = pd.read_csv(input_file)

        table_counts = []
        col_counts = []
        fkey_counts = []

        for i in range(len(df)):
            row = df.iloc[i]
            db_id = row['db_id']
            stats = schema_stats[db_id]

            table_counts.append(stats['num_tables'])
            col_counts.append(stats['num_columns'])
            fkey_counts.append(stats['num_foreign_keys'])

        df['num_tables'] = table_counts
        df['num_columns'] = col_counts
        df['num_foreign_keys'] = fkey_counts

        df.to_csv(output_file, index=False)

if __name__ == '__main__':

    schema_stats_file = 'schema_stats.json'
    input_file = 'data/spider/test_with_metadata.csv'
    output_file = input_file

   