import json
import pandas as pd
from preprocess.tokenize_query import tokenize
from sqlglot import parse_one, expressions as exp, ParseError
from other_utils.deserialize_db_model import deserialize_db_schema_model
from evaluation.canonical_query_representation import *
#from utils.process_sql import *

class Schema:
    """
    Simple schema which maps table&column to a unique identifier
    """
    def __init__(self, schema, table):
        self._schema = schema
        self._table = table
        self.idMap = self._map(self._schema, self._table)

    @property
    def schema(self):
        return self._schema

    @property
    def get_idMap(self):
        return self.idMap

    def _map(self, schema, table):
        column_names_original = table['column_names_original']
        table_names_original = table['table_names_original']
        idMap = {'*' : -1}
        for i, (tab_id, col) in enumerate(column_names_original):
            key = table_names_original[tab_id].lower()
            val = col.lower()
            idMap[key + "." + val] = i

        for i, tab in enumerate(table_names_original):
            key = tab.lower()
            idMap[key] = i

        self.idMap = idMap
        return self.idMap
    
def scan_alias(toks):
    """Scan the index of 'as' and build the map for all alias"""
    as_idxs = [idx for idx, tok in enumerate(toks) if tok == 'as']
    alias = {}
    for idx in as_idxs:
        alias[toks[idx+1]] = toks[idx-1]
    return alias

def get_tables_with_alias(schema, toks):
    tables = scan_alias(toks)
    for key in schema:
        assert key not in tables, "Alias {} has the same name in table".format(key)
        tables[key] = key
    return tables

def get_reformatted(schemas, db_id):
    db_names = list(schemas.keys())
    schema = schemas[db_id]
    #Object representing schema with table name as key and columns as corresponding values
    simplified_schema = {}
    simplified_tables = {}
    for table in schema.tables:
        simplified_schema[table.name.lower()] = [col_name.lower() for col_name in table.attributes.keys()]

    simplified_tables["table_names_original"] = [table.name for table in schema.tables]
    simplified_tables["column_names_original"] = [(idx, col_name.lower()) for idx, table in enumerate(schema.tables) for col_name in table.attributes.keys()]

    return simplified_schema, db_names, simplified_tables

class SQLStandardizer:

    def __init__(self, query: str, ast = None): 
        try:
            self.ast = parse_one(query) if not ast else ast
        except ParseError:
            raise ValueError("Query is syntactically incorrect, unable to be parsed!")
        self.query = query
        self.IUE_PARSED = False
        self.standardized_query = {}
        self.default_tables = []

    def get_sql(self):
        if "case when" in self.query:
            raise NotImplementedError("Case function isn't handled yet!")
        self.parse_sql()
        return self.standardized_query
    
    def parse_sql(self):
        components = self.ast.args
        if self.ast.key in SQL_OPS:
            self.standardized_query[self.ast.key] = True
            response = self.parse_IUE(components.get('this'), components.get('expression'))
            left, right = response
            self.standardized_query['left_query'] = left
            self.standardized_query['right_query'] = right
        else:
            for op in SQL_OPS:
                self.standardized_query[op] = False
            
        if not self.IUE_PARSED:
            isDistinct = bool(components.get("distinct"))
            table_units, conds = self.parse_from(components.get('from_', None), 
                                                 components.get('joins', []))
            self.standardized_query['from'] = {'table_units' : table_units, 'conds' : conds}
            self.standardized_query['select'] = (isDistinct, self.parse_select(components.get('expressions')))
            self.standardized_query['where'] = self.parse_where_or_having(components.get('where', None))
            self.standardized_query['having'] = self.parse_where_or_having(components.get('having', None))
            self.standardized_query['group_by'] = self.parse_group_by(components.get('group', []))
            self.standardized_query['order_by'] = self.parse_order_by(components.get('order', []))
            self.standardized_query['limit'] = self.parse_limit(components.get('limit', None))


    def parse_IUE(self, left_query, right_query):
        if left_query is None or right_query is None:
            return None
        self.IUE_PARSED = True
        left_std = SQLStandardizer(left_query.sql(), left_query).get_sql()
        right_std = SQLStandardizer(right_query.sql(), right_query).get_sql()

        return left_std, right_std


    def parse_select(self, expressions):
        def unwrap_alias(expr):
            return unwrap_alias(expr.this) if isinstance(expr, exp.Alias) else expr
        
        val_units = []
        for expr in expressions:
            expr = unwrap_alias(expr)
            val_unit = self.parse_val_unit(expr)
            val_units.append(val_unit)

        return val_units
    
    def parse_where_or_having(self, expr):
        if expr == None:
            return expr
        return self.parse_condition(expr.this)

    def parse_group_by(self, group_expr : exp.Group):
        if group_expr == []:
            return None
        group_units = []
        for gexpr in group_expr.expressions:
            col_unit = self.parse_col_unit(gexpr)
            group_units.append(col_unit)
        return group_units
    
    def parse_order_by(self, order_expr : exp.Order):
        if order_expr == []:
            return None
        val_units = []
        for order_by in order_expr.expressions:
            val_unit = self.parse_val_unit(order_by.this)
            order = 'desc' if order_by.args['desc'] else 'asc'
            val_units.append((val_unit, order))
        return val_units
    
    def parse_limit(self, limit_node):
        if limit_node:
            return int(limit_node.expression.name)
        else:
            return None

    def parse_table_unit(self, table_expr):
        """Returns the table id and the table name (resolved)"""
        resolved_table_name = table_expr.this.name
        table_id = SQLStandardizer.schema.idMap[resolved_table_name]
        return table_id, resolved_table_name

    def get_column_id(self, column_expr):
        """Returns the standardized id for a column (a consistent value across queries)"""
        assert isinstance(column_expr, (exp.Column, exp.Star)), "Expected Column expression!"
        col = column_expr.name  
        table_alias = column_expr.table if col != '*' else None

        if col == '*':
            return SQLStandardizer.schema.idMap['*']
        elif table_alias:
            alias_mapping = SQLStandardizer.tables_with_alias.get(table_alias.lower())
            if isinstance(alias_mapping, dict):
                # subquery schema
                if col not in alias_mapping:
                    raise ValueError(f"Column {col} not found in subquery alias {table_alias}")
                return alias_mapping[col]
            else:
                # base table name
                key = alias_mapping + '.' + col
                return SQLStandardizer.schema.idMap[key]
        else:
            for table_name in self.default_tables:
                if col in SQLStandardizer.schema.schema[table_name]:
                    return SQLStandardizer.schema.idMap[table_name + '.' + col]

    def parse_from(self, from_clause, joins):
        """Assume in the from clause, all table units are combined with join"""
        table_units = []
        base_table_expr = from_clause.this
        
        if isinstance(base_table_expr, exp.Table):
            table_id, table_name = self.parse_table_unit(base_table_expr)
            table_units.append(TableUnit(TABLE_TYPE['table_unit'], table_id, None))
            self.default_tables.append(table_name)
        elif isinstance(base_table_expr, exp.Subquery):
            sql = SQLStandardizer(base_table_expr.this.sql(), base_table_expr.this).get_sql()
            alias = base_table_expr.alias_or_name.lower()
            table_units.append((TABLE_TYPE['sql'], sql, None))
            
        return self.parse_explicit_joins(joins, table_units)


    def parse_explicit_joins(self, joins, table_units : list):
        """Add explicitly joined tables and join conditions"""
        conds = []
        for join in joins:
            join_table_expr = join.this
            on_condition = join.args.get('on') 

            if isinstance(join_table_expr, exp.Table):
                table_id, table_name = self.parse_table_unit(join_table_expr)
                kind = str(join.args.get('kind', 'INNER')).upper()
                table_units.append(TableUnit(TABLE_TYPE['table_unit'], table_id, kind))
                self.default_tables.append(table_name)
            elif isinstance(join_table_expr, exp.Subquery):
                sql = SQLStandardizer(join_table_expr.this.sql(), join_table_expr.this).get_sql()
                kind = str(join.args.get('kind', 'INNER')).upper()
                table_units.append((TABLE_TYPE['sql'], sql, kind))
            
            join_conds = self.parse_condition(on_condition)
            if len(conds) > 0:
                conds.append('and')
            conds.extend(join_conds)
        
        return table_units, conds

    def parse_condition(self, condition):
        """Returns a list of cond_units linked by and/or"""
        WHERE_OP_TYPES = tuple(op for op in WHERE_OPS.values() if op is not None)
        if condition is None:
            return []
        elif isinstance(condition, WHERE_OP_TYPES):
            cond_unit = self.parse_atomic_condition(condition)
            return [cond_unit]
        elif isinstance(condition, (exp.And, exp.Or)):
            connector = condition.key.lower()
            return self.parse_condition(condition.this) + [connector.lower()] + self.parse_condition(condition.expression)
        else:
            return []
        
    def parse_atomic_condition(self, expr):
        not_op = False
        val_unit = None
        val1 = val2 = None

        if isinstance(expr, exp.Not):
            not_op = True
            expr = expr.this

        op_id = expr.key.lower()

        if isinstance(expr, exp.Between):
            val1 = self.parse_value(expr.args['low'])
            val2 = self.parse_value(expr.args['high'])
            val_unit = self.parse_val_unit(expr.this)
        elif isinstance(expr, exp.In):
            if expr.args.get('expressions'):
                val1 = [self.parse_value(e) for e in expr.args['expressions']]
            elif expr.args.get("query"):  
                subquery = expr.args["query"]
                val1 = self.parse_value(subquery)
            val_unit = self.parse_val_unit(expr.this)
        else:
            val_unit = self.parse_val_unit(expr.left)
            val1 = self.parse_value(expr.right)

        return CondUnit(not_op, op_id, val_unit, val1, val2)
        

    def parse_val_unit(self, expr):
        """Forms an expression combining val_units and col_units with unit_ops (+, -, /, *)"""
        UNIT_OP_TYPES = tuple(op for op in UNIT_OPS.values() if op is not None)
        if isinstance(expr, exp.Paren):
            expr = expr.this

        if isinstance(expr, UNIT_OP_TYPES):
            left = self.parse_val_unit(expr.this)
            right = self.parse_val_unit(expr.expression)
            return ValUnit(expr.key.lower(), left, right)
        else:
            try:
                col_unit = self.parse_col_unit(expr)
                return ValUnit('none', col_unit, None)
            except ValueError:
                return ValUnit('none', self.parse_value(expr), None)


    def parse_col_unit(self, expr):
        AGG_OP_TYPES = tuple(op for op in AGG_OPS.values() if op is not None)

        if isinstance(expr, exp.Paren):
            expr = expr.this

        if isinstance(expr, AGG_OP_TYPES):
            agg_op = expr.sql_name().lower()
            inner_expr = expr.this
            if isinstance(inner_expr, exp.Distinct):
                is_distinct = True
                col_expr = inner_expr.expressions[0]
            elif isinstance(inner_expr, (exp.Column, exp.Star)):
                is_distinct = False
                col_expr = inner_expr
            col_id = self.get_column_id(col_expr)
            return ColUnit(agg_op, col_id, is_distinct)
        
        elif isinstance(expr, (exp.Column, exp.Star)):
            col_id = self.get_column_id(expr)  
            return ColUnit(None, col_id, False)
        
        else:
            raise ValueError("Unit can't be parsed as a column unit!")


    def parse_value(self, value_node):
        """Extracts a 'value' term: a string/float literal, nested subquery representation, or a column unit)"""
        if isinstance(value_node, exp.Paren):
            value_node = value_node.this
        
        if isinstance(value_node, exp.Null):
            return "null"
        if isinstance(value_node, exp.Subquery):
            return SQLStandardizer(value_node.this.sql(), value_node.this).get_sql()
        elif isinstance(value_node, exp.Boolean):
            return value_node.this.lower() == "true"
        elif isinstance(value_node, exp.Literal):
            try:
                return float(value_node.this)
            except ValueError:
                return value_node.this
        else:
            return self.parse_col_unit(value_node)


def parse_sql_query(sql: str, schema, db_id: str):
    """Helper to parse a SQL query into its structured representation. 
    Returns None if parsing fails, along with error type."""
    try:
        sql = sql.replace('"', "'")
        tokens = tokenize(sql)
        tables_with_alias = get_tables_with_alias(schema.schema, tokens)

        SQLStandardizer.schema = schema
        SQLStandardizer.tables_with_alias = tables_with_alias
        parser = SQLStandardizer(sql.lower())

        parsed_rep = parser.get_sql()
        return parsed_rep, None
    except ValueError:
        return None, "syntacticallyIncorrect"
    except NotImplementedError:
        return None, "unhandled"
    except KeyError:
        return None, "schemaLinkingError"
    except Exception as e:
        #print("An exception occurred:", e)
        return None, "other"


def run_parser_on_dataset(dataset: str, output_file: str, schemas: map):
    """Parses both gold and predicted queries, writes them + parsed reps to output."""
    df = pd.read_csv(dataset, quotechar='"', doublequote=True)

    # Storage for results
    gold_queries, pred_queries = [], []
    gold_parsed, pred_parsed = [], []
    questions = []

    # Error counters
    counts = {"unhandled": 0,
              "schemaLinkingError": 0,
              "syntacticallyIncorrect": 0,
              "other": 0}

    for _, sample in df.iterrows():
        db_id = sample['db_id']
        question = sample['question']
        gold_query = sample['query']
        pred_query = sample['pred_query']

        schema, _, table = get_reformatted(schemas, db_id)
        schema = Schema(schema, table)

        # Parse both queries
        gold_rep, gold_err = parse_sql_query(gold_query, schema, db_id)
        pred_rep, pred_err = parse_sql_query(pred_query, schema, db_id)

        if gold_err: counts[gold_err] += 1
        if pred_err: counts[pred_err] += 1

        # Store results
        if gold_err is None and pred_err is None:
            questions.append(question)
            gold_queries.append(gold_query)
            pred_queries.append(pred_query)
            gold_parsed.append(gold_rep)
            pred_parsed.append(pred_rep)

    # Write results to file
    output_df = pd.DataFrame({
        "question": questions,
        "gold_query": gold_queries,
        "gold_parsed_rep": gold_parsed,
        "pred_query": pred_queries,
        "pred_parsed_rep": pred_parsed
    })
    #output_df.to_csv(output_file, index=False)

    return counts, questions, gold_parsed, pred_parsed



if __name__ == '__main__':

    schemas = deserialize_db_schema_model('data/spider/interim_db_schemas_object')
    # error_breakdown, questions, g_parsed, p_parsed = run_parser_on_dataset('combined.csv', "test_parsed_reps.csv", schemas)
    # print(error_breakdown)

    # Sample query parsing:
    sql = "SELECT T2.name ,  count(*) FROM concert AS T1 JOIN stadium AS T2 ON T1.stadium_id  =  T2.stadium_id GROUP BY T1.stadium_id"
    sql = sql.replace('"', "'")
    db_id = 'concert_singer'
    schema, db_names, table = get_reformatted(schemas, db_id)
    schema = Schema(schema, table)
    tokens = tokenize(sql)
    tables_with_alias = get_tables_with_alias(schema.schema, tokens)
    SQLStandardizer.schema = schema
    SQLStandardizer.tables_with_alias = tables_with_alias
    print(schema.idMap)
    print(tables_with_alias)
    
    parser = SQLStandardizer(sql.lower())
    components = parser.ast.args
    print(components)
    print(parser.get_sql())
    
    





            