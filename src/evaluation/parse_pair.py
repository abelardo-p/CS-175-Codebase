from evaluation.process_query import *
from evaluation.structural_evaluate import *

def parse_sql(query: str, schemas, db_id):
    query = query.replace('"', "'")
    schema, _, table = get_reformatted(schemas, db_id)
    schema = Schema(schema, table)
    tokens = tokenize(query)
    tables_with_alias = get_tables_with_alias(schema.schema, tokens)
    SQLStandardizer.schema = schema
    SQLStandardizer.tables_with_alias = tables_with_alias
    parser = SQLStandardizer(query.lower())
    return parser.get_sql()

def score_pair(gold_query: str, pred_query: str, schemas, db_id) -> dict:
    """Takes a pair of query strings as input and returns partial scores scross the sql clauses"""
    gold_parsed = parse_sql(gold_query, schemas, db_id)
    pred_parsed = parse_sql(pred_query, schemas, db_id)
    # print(gold_parsed)
    # print(pred_parsed)
    scores = compare_sql_components(gold_parsed, pred_parsed)
    return scores


if __name__ == '__main__':

    schemas = deserialize_db_schema_model('data/spider/interim_db_schemas_object')
    # gold_sql = "SELECT weight FROM pets ORDER BY pet_age LIMIT 1"
    # pred_sql = "SELECT T1.weight FROM pets AS T1 INNER JOIN has_pet AS T2 ON T1.petid = T2.petid WHERE T1.pettype = 'Dog' ORDER BY T1.pet_age LIMIT 1"
    gold_sql = "SELECT T1.fname ,  T1.sex FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid GROUP BY T1.stuid HAVING count(*)  >  1"
    pred_sql = "SELECT T2.fname, T2.sex FROM has_pet AS T1 INNER JOIN student AS T2 ON T1.stuid = T2.stuid GROUP BY T2.fname, T2.sex, T2.stuid HAVING COUNT(T1.petid) > 1"
    
    scores = score_pair(gold_sql, pred_sql, schemas, "pets_1")
    pprint.pprint(scores, indent=4, width=80)