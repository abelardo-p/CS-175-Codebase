from sql_metadata import Parser
import sqlglot
from sqlglot import parse_one, expressions as exp
from metadata_utils.hardness_level import classify
from metadata_utils.sql_features import SQLFeatures
from dataclasses import asdict

HARDNESS = {
    "component1": ('where', 'group', 'order', 'limit', 'join', 'or', 'like'),
    "component2": ('except', 'union', 'intersect')
}

class QueryComplexity:

    """Takes in a dict representing the json for a query-containing sample"""
    def __init__(self, sample : dict):
        self.query = sample.get('query')
        self.tokens = [token.lower() for token in sample.get('query_toks')]
        if self.query is None or self.tokens is None:
            raise AttributeError('query or query tokens not provided')
        self.feature_set = None

    def get_hardness_level(self) -> str:
        """Classifies the query 'hardness' as defined in hardness_criteria """
        self.extract_features()
        return classify(self.feature_set)
    
    def extract_features(self):
        """Extracts features of this query as defined in SQLFeatures"""
        self.feature_set = SQLFeatures()
        for comp in HARDNESS['component1']:
            if comp.lower() in self.tokens:
                self.feature_set.num_components_1 += 1
        for comp in HARDNESS['component2']:
            if comp.lower() in self.tokens:
                self.feature_set.num_components_2 += 1
        
        self.feature_set.num_agg = self.count_aggregates()
        self.feature_set.num_select_cols = self.count_select_columns()
        self.feature_set.num_where_conditions = self.count_where_conditions()
        self.feature_set.num_group_by = self.count_group_by()

        self.feature_set.query_length = self.get_query_length()
        self.feature_set.num_table_aliases = self.get_involved_tables()
        self.feature_set.num_joins = self.get_num_joins()
        self.feature_set.num_order_attributes = self.count_order_by()

        self.feature_set.has_subquery = self.has_subquery()
        self.feature_set.has_limit = self.has_limit()
        self.feature_set.has_order_by = self.has_order_by()
        
    def get_query_length(self):
        """"Returns the number of tokens in the given query"""
        return len(self.tokens) if self.tokens is not None else 0

    def get_involved_tables(self):
        """Gets the number of table aliases (not just distinct table names) to account for self-joins"""
        aliases = (Parser(self.query)).tables_aliases
        return len(aliases)

    def num_tables_used(self):
        return len(Parser(self.query).tables)

    def get_num_joins(self):
        """Number of joins is tracked since #involved tables is not always 1:1 with #joins"""
        return sum(1 for token in self.tokens if token.lower() == 'join')

    def count_aggregates(self):
        aggregates = ['min', 'max', 'count', 'sum', 'avg']
        return sum(1 for token in self.tokens if token in aggregates)

    def has_subquery(self):
        return "select" in self.tokens and self.tokens.count("select") > 1
    
    def has_limit(self):
        return "limit" in self.tokens

    def has_order_by(self):
        return "order" in self.tokens

    def count_select_columns(self):
        try:
            sql_ast = sqlglot.parse_one(self.query)
            select_exprs = sql_ast.find_all(exp.Select)
            return sum(len(expr.expressions) for expr in select_exprs)
        except Exception as e:
            print(f"Failed to count SELECT columns: {e}")
            return -1

    def _count_conditions_recursive(self, expr):
        #print(f"Visiting: {expr} | type: {type(expr)}")
        if isinstance(expr, (exp.And, exp.Or)):
            sub_exprs = expr.flatten()
            return sum(self._count_conditions_recursive(e) for e in sub_exprs)
        elif is_condition_node(expr):
            return 1
        else:
            return 0

    def count_where_conditions(self):
        try:
            sql_ast = sqlglot.parse_one(self.query)
            total_count = 0
            for where_expr in sql_ast.find_all(exp.Where):
                total_count += self._count_conditions_recursive(where_expr.this)
            return total_count
        except Exception as e:
            print(f"Failed to parse or count WHERE conditions: {e}")
            return -1
    
    def count_group_by(self):
        try:
            sql_ast = sqlglot.parse_one(self.query)
            total_count = 0
            for group_by_expr in sql_ast.find_all(exp.Group):
                total_count += len(group_by_expr.expressions)
            return total_count
        except Exception as e:
            print(f"Failed to parse or count GROUP BY conditions: {e}")
            return -1
    
    def count_order_by(self):
        try:
            sql_ast = sqlglot.parse_one(self.query)
            total_count = 0
            for order_expr in sql_ast.find_all(exp.Order):
                total_count += len(order_expr.expressions)
            return total_count
        except Exception as e:
            print(f"Failed to parse or count ORDER BY conditions: {e}")
            return -1

def is_condition_node(node):
    return isinstance(node, (
        exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE,
        exp.Like, exp.ILike, exp.In, exp.Between, exp.Is,
        exp.Exists
    ))

    
if __name__ == '__main__':

    # Sample usage 
    query = "SELECT DISTINCT T1.creation FROM department AS T1 JOIN management AS T2 ON T1.department_id  =  T2.department_id JOIN head AS T3 ON T2.head_id  =  T3.head_id WHERE T3.born_state  =  'Alabama'"
    tokens = ['select', 'distinct', 't1.creation', 'from', 'department', 'as', 't1', 'join', 'management', 'as', 't2', 'on', 't1.department_id', '=', 't2.department_id', 'join', 'head', 'as', 't3', 'on', 't2.head_id', '=', 't3.head_id', 'where', 't3.born_state', '=', '"Alabama"']
    input_dict = {'query' : query, "query_toks" : tokens}
    qc = QueryComplexity(input_dict)
    print(qc.get_hardness_level())
    print(asdict(qc.feature_set))