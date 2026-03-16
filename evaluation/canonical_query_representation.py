# Canonical SQL Query Representation for Evaluation

# Assumptions:
#   1. Only table names are aliased
#   2. The LIMIT value is an explicit numerical type
#   3. only one of intersect/union/except

# -------------------------------------------------------------------------------------------------
# Core Building Blocks
# -------------------------------------------------------------------------------------------------

# val: Represents a literal value.
#   Type: float | str | dict (for nested SQL subqueries)
#   Examples:
#     - 123.45 (float)
#     - "Product A" (str)
#     - { 'select': ..., 'from': ... } (dict, for a subquery)

# col_unit: Represents a reference to a column, optionally with an aggregation and distinct modifier.
#   Type: tuple
#   Format: (agg_id: int, col_id: int, isDistinct: bool)
#   Notes:
#     - agg_id: Integer identifier for aggregation function (e.g., 0: NONE, 1: COUNT, 2: SUM, 3: AVG, 4: MIN, 5: MAX)
#     - col_id: Integer identifier for the column.
#     - isDistinct: True if DISTINCT is applied to the column within the aggregation (e.g., COUNT(DISTINCT column)), otherwise False.
#   Example: (1, 5, True) # COUNT(DISTINCT col_id_5)

# val_unit: Represents an expression yielding a value (e.g., a column, a literal, or an arithmetic operation).
#   Type: tuple
#   Format: (unit_op: int, operand1: val_unit | col_unit | value, operand2: val_unit | col_unit | value)
#   Notes:
#     - unit_op: Integer identifier for the operation (e.g., 0: NONE, 1: +, 2: -, 3: *, 4: /).
#     - operand1, operand2: Can be either a col_unit (base column/literal) or another val_unit (for nested expressions).
#       - If unit_op is NONE, operand1 is the value/column and operand2 is None.
#       - If operand2 is not applicable for a unary operation, it's None.
#   Examples:
#     - (0, (0, 10, False), None)      # Represents col_id_10
#     - (1, (0, 10, False), (0, 11, False)) # col_id_10 + col_id_11
#     - (3, (0, 10, False), (1, (0, 11, False), (0, 12, False))) # col_id_10 * (col_id_11 + col_id_12)

# table_unit: Represents a table or a subquery in the FROM clause, including join type.
#   Type: tuple
#   Format: (table_type: int, table_id_or_sql: int | dict, join_type: str | None)
#   Notes:
#     - table_type: Integer identifier (e.g., 0: Table, 1: SQL subquery).
#     - table_id_or_sql: Integer identifier for a table, or a 'sql' dict for a subquery.
#     - join_type: Type of join as a string ('INNER', 'LEFT', 'RIGHT', 'FULL', 'CROSS', or None for implicit joins/single table).
#   Examples:
#     - (0, 1, None) # A base table with table_id 1
#     - (0, 2, 'INNER') # Table with table_id 2, part of an INNER JOIN
#     - (1, { 'select': ..., 'from': ... }, 'LEFT') # A subquery joined with LEFT

# cond_unit: Represents a single predicate (condition unit) in WHERE or HAVING clauses.
#   Type: tuple
#   Format: (not_op: bool, op_id: int, operand: val_unit, val1: col_unit | val, val2: val | None)
#   Notes:
#     - not_op: True if NOT is applied to the condition (e.g., NOT (A = B)), otherwise False.
#     - op_id: Integer identifier for the comparison operator (e.g., 0: =, 1: >, 2: <, 3: >=, 4: <=, 5: !=, 6: LIKE, 7: IS, 8: IN, 9: BETWEEN).
#     - operand: The val_unit on the left-hand side of the comparison.
#     - val1: The first value/literal on the right-hand side.
#     - val2: The second value/literal (used for BETWEEN, otherwise None).
#     - For 'IS' operator (op_id 7), val1 would typically be 'NULL' or 'NOT NULL'.
#     - For 'IN' operator (op_id 8), val1 can be a list of `val`s or a `sql` dict (subquery).
#   Examples:
#     - (False, 0, (0, (0, 1, False), None), 100, None) # col_id_1 = 100
#     - (True, 5, (0, (0, 2, False), None), "Active", None) # NOT col_id_2 != "Active"
#     - (False, 9, (0, (0, 3, False), None), 10, 20) # col_id_3 BETWEEN 10 AND 20

# condition: A list representing a sequence of cond_units joined by logical operators.
#   Type: list
#   Format: [cond_unit1, logical_op_str1, cond_unit2, logical_op_str2, ..., cond_unitN]
#   Notes:
#     - logical_op_str: 'and' or 'or'.
#   Example: [(False, 0, (0, (0, 1, False), None), 100, None), 'and', (False, 1, (0, (0, 2, False), None), 50, None)] # col_id_1 = 100 AND col_id_2 > 50

# -------------------------------------------------------------------------------------------------
# SQL Query Structure
# -------------------------------------------------------------------------------------------------

# sql: Represents a complete SQL query or a subquery. This structure is recursive.
#   Type: dict
#   Format:
#   {
#     'select': (isDistinct: bool, select_expressions: list)
#       - isDistinct: True if SELECT DISTINCT, False otherwise.
#       - select_expressions: List of (val_unit: val_unit) for selected columns/expressions.
#     'from': {'table_units': list, 'conds': condition}
#       - table_units: List of table_unit tuples.
#       - conds: A 'condition' list representing join conditions (if any explicit ON clauses, else []).
#     'where': condition | None
#       - condition: A 'condition' list for the WHERE clause. None if no WHERE clause.
#     'group_by': list | None
#       - List of col_unit for GROUP BY columns. None if no GROUP BY clause.
#     'order_by': list | None
#       - List of (val_unit: val_unit, direction: str) tuples.
#       - direction: 'asc' or 'desc'.
#       - None if no ORDER BY clause.
#     'having': condition | None
#       - A 'condition' list for the HAVING clause. None if no HAVING clause.
#     'limit': int | None
#       - The LIMIT value. None if no LIMIT clause.
#     'intersect': True | False
#       - True if the current (top-level) query is an intersect.
#     'except': True | False
#       - True if the current (top-level) query is an except.
#     'union': True | False
#       - True if the current (top-level) query is an union.
#   }
#   *The sql dict will contain keys 'left' and 'right' if the top-level query is an intersect/except/union. These keys represent the queries being IEU'd on, respectively.

from typing import Any, Optional, Union
from sqlglot import parse_one, expressions as exp
from typing import NamedTuple

CLAUSE_KEYWORDS = ('select', 'from', 'where', 'group', 'order', 'limit', 'intersect', 'union', 'except')
JOIN_KEYWORDS = ('join', 'on', 'as')

WHERE_OPS = {
    "not": exp.Not,
    "between": exp.Between,
    "=": exp.EQ,
    ">": exp.GT,
    "<": exp.LT,
    ">=": exp.GTE,
    "<=": exp.LTE,
    "!=": exp.NEQ,
    "in": exp.In,
    "like": exp.Like,
    "is": exp.Is,
    "exists": exp.Exists,
}
COMMUTATIVE_OPS = {"eq", "neq"}
OPPOSING_SIGNS = {
    'gt': 'lt',
    'lt': 'gt',
    'geq': 'leq',
    'leq': 'geq'
    }

UNIT_OPS = {
    'none': None,       
    '-': exp.Sub,       
    '+': exp.Add,       
    '*': exp.Mul,      
    '/': exp.Div,       
}

AGG_OPS = {
    'none': None,
    'max': exp.Max,
    'min': exp.Min,
    'count': exp.Count,
    'sum': exp.Sum,
    'avg': exp.Avg,
}

TABLE_TYPE = {
    'sql': "sql",
    'table_unit': "table_unit",
}

COND_OPS = ('and', 'or')
SQL_OPS = ('intersect', 'union', 'except')
ORDER_OPS = ('desc', 'asc')

class ColUnit(NamedTuple):
    agg_id: str           
    col_id: int           # column identifier
    isDistinct: bool      # DISTINCT applied or not

class ValUnit(NamedTuple):
    unit_op: int            # 0: NONE, 1: +, 2: -, 3: *, 4: /
    operand1: Union['ValUnit', ColUnit, 'Value']
    operand2: Union['ValUnit', ColUnit, 'Value']

class TableUnit(NamedTuple):
    table_type: str                      # 'sql' or 'table_unit'
    table: Union[int, dict]              # resolved table id or nested sql dict
    join_type : Optional[str] = None                     

class CondUnit(NamedTuple):
    not_op: bool          # True if NOT is applied
    op_id: str            # Refer to WHERE_OPS
    operand: ValUnit
    val1: Union[ColUnit, Any]
    val2: Optional[Any]
