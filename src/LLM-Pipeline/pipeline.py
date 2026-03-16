from ollama import chat
from ollama import ChatResponse
from pathlib import Path
import pandas as pd
import json 
from format import *
# from google.colab import files

PREFIX = "```sql\n"
SUFFIX = "```"

# input file csv: = db_id,question,query,query_toks

class Pipeline:
    def __init__(self, model: str, system_prompt: str, assumption: str, data_path: Path, data_scheme_path):
        self.model = model
        self.system_prompt = system_prompt
        self.assumption = assumption
        self.data_scheme_path = data_scheme_path
        self.data_path = data_path


    def promptLLM(self, prompt: list[str]) -> str:
        response: ChatResponse = chat(model=self.model, messages=[
            {
                'role': 'system',
                'content': prompt[0],
            },
            {   
                'role': 'user',
                'content': prompt[1]
            },
        ])
        return response['message']['content']

    def run(self):
        with open(self.data_scheme_path, "r") as f:
            db_schemas = json.load(f)
        df = pd.read_csv(self.data_path)

        result_map = {
            "db_id": [],
            "question": [],
            "query": [],
            "pred_query": [],
            }

        prompt = None
        for i in range(len(df)):
            curr_row = df.iloc[i]
            db_id = curr_row['db_id']
            question = curr_row['question']
            query = curr_row['query']
            db = db_schemas[db_id]
            schema = db['ddl_string'].lower()

            prompt = formatPrompt(self.system_prompt, self.assumption, schema, question)

            predicted_sql = self.promptLLM(prompt)
            predicted_sql = formatOutput(PREFIX, SUFFIX, predicted_sql)
            
            result_map['db_id'].append(db_id)
            result_map['question'].append(question)
            result_map['query'].append(query)
            result_map['pred_query'].append(predicted_sql)

            if i % 25 == 0:
                print(i, "/", len(df))
                break
        result_df = pd.DataFrame(result_map)
        result_df.to_csv(f"./dataset/predictions-{self.model.   }.csv", index=False)


def main():
    models = [
        'gemma3:1b',
        'gemma3:4b',
        'gemma3:12b',
        'qwen3:0.6b',
        'qwen3:1.7b',
        'qwen3:4b',
        'qwen3:8b',
        'qwen:14b'
        #deepseek-model?
    ]
    model = models[0]
    data_path = Path('../text2sql-eval/data/spider/datasets_original/test_dataset.csv')
    data_scheme_path = Path('../text2sql-eval/db_schemas_with_complexity.json')

    system_prompt = 'You are a text-to-SQL assistant. Generate a correct SQL query that adheres to the given assumptions, using only the question and database schema, and nothing else. Do not include any additional non SQL content such as comments or formatting'
    assumption = "# Assumptions for generating the SQL query:\n# 1. Only table names are aliased\n# 2. LIMIT value is always a numerical type\n# 3. Only one of INTERSECT / UNION / EXCEPT can be used"

    pipeline = Pipeline(model, system_prompt, assumption, data_path, data_scheme_path)
    pipeline.run()

if __name__ == '__main__':
    main()


