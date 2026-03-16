import pickle
import json
from canonicalized_data_format.ddl_objects import DBSchemaModel

def deserialize_db_schema_model(load_path : str) -> dict[str : DBSchemaModel]:
    """Returns the db schemas as a dict with keys representing the db_id and values are the standardized schema objects"""
    print(load_path)
    with open(load_path, 'rb') as file:
        loaded_db_schemas = pickle.load(file)
        return loaded_db_schemas


if __name__ == '__main__':

    load_path = 'data/spider/interim_db_schemas_object'
    db_schemas = deserialize_db_schema_model(load_path)
    print(len(db_schemas))
    
    # db_string_reps = {}
    # for db in db_schemas:
    #     schema = db_schemas[db]
    #     db_string_reps[db] = {"ddl_string" : schema.get_ddl_string(), "schema_complexity": schema.get_db_schema_complexity()}

    # with open('db_schemas_with_complexity.json', 'w') as f:
    #     json.dump(db_string_reps, f, indent=2)
