from evaluation.canonical_query_representation import *
from collections import Counter
from evaluation.process_query import *

score_keys = ['explicit_join_conds', 'from', 'group', 'group_by_having', 'limit', 'order', 'select', 'where']

# ---------- small PRF helpers ----------
def safe_prf1(matches, gold_count, pred_count):
    precision = matches / pred_count if pred_count else 0
    recall = matches / gold_count if gold_count else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {"precision": precision, "recall": recall, "f1": f1}

def unordered_structural_match(gold_list, pred_list, equal_fn):
    """Greedy set-like matching for unhashable elements.
    Returns: (matches, len(gold_list), len(pred_list))
    """
    matches = 0
    used_pred = set()

    for gold in gold_list:
        for i, pred in enumerate(pred_list):
            if i not in used_pred and equal_fn(gold, pred):
                matches += 1
                used_pred.add(i)
                break
    return matches, len(gold_list), len(pred_list)

def ordered_structural_match(gold_list, pred_list, equal_fn):
    """Match pairwise by position. gold_list and pred_list are sequences.
    Returns: (matches, len(gold_list), len(pred_list))
    """
    matches = 0
    for gold, pred in zip(gold_list, pred_list):
        # gold and pred may be tuples (val_unit, dir) in order_by; equal_fn should handle inner units
        if isinstance(gold, tuple) and isinstance(pred, tuple):
            g_unit, g_meta = gold
            p_unit, p_meta = pred
            if g_meta == p_meta and equal_fn(g_unit, p_unit):
                matches += 1
        else:
            if equal_fn(gold, pred):
                matches += 1
    return matches, len(gold_list), len(pred_list)

# ---------- column extraction ----------
def extract_all_col_units(unit):
    """Return list of ColUnit objects contained in unit (ColUnit or nested ValUnit)."""
    if isinstance(unit, ColUnit):
        return [unit]
    if isinstance(unit, ValUnit):
        left = extract_all_col_units(getattr(unit, "operand1", None))
        right = extract_all_col_units(getattr(unit, "operand2", None))
        return left + right
    return []

# ---------- operand / value equality ----------
def _is_col_wrapper(val_unit):
    """True if ValUnit wraps a single ColUnit (operand1 is ColUnit and operand2 is None)."""
    return isinstance(val_unit, ValUnit) and isinstance(getattr(val_unit, "operand1", None), ColUnit) and getattr(val_unit, "operand2", None) is None

def operand_equal(op1: Any, op2: Any) -> bool:
    """Robust operand equality that delegates into ValUnit and ColUnit handling."""
    if op1 is None and op2 is None:
        return True
    if op1 is None or op2 is None:
        return False

    if isinstance(op1, ValUnit) and isinstance(op2, ValUnit):
        return equal_val_units(op1, op2)

    if isinstance(op1, ValUnit) and _is_col_wrapper(op1) and isinstance(op2, ColUnit):
        return getattr(op1, "operand1") == op2
    if isinstance(op2, ValUnit) and _is_col_wrapper(op2) and isinstance(op1, ColUnit):
        return getattr(op2, "operand1") == op1

    if isinstance(op1, dict) and isinstance(op2, dict):
        return equal_sql_dict(op1, op2)

    if type(op1) == type(op2):
        return op1 == op2

    return False

def equal_val_units(gold: ValUnit, pred: ValUnit):
    """Compare ValUnit structures (operator + operands); supports commutativity for add/mul."""
    g_unit_op, g_operand1, g_operand2 = gold
    p_unit_op, p_operand1, p_operand2 = pred
    
    if g_unit_op != p_unit_op:
        return False
    
    if g_unit_op.lower() in ('sub', 'div'):
        if type(g_operand1) != type(p_operand1) or type(g_operand2) != type(p_operand2):
            return False
        return operand_equal(g_operand1, p_operand1) and operand_equal(g_operand2, p_operand2)
    elif g_unit_op.lower() in ('add', 'mul'):
        return (operand_equal(g_operand1, p_operand1) or operand_equal(g_operand1, p_operand2)) and \
                (operand_equal(g_operand2, p_operand1) or operand_equal(g_operand2, p_operand2))
    else:
        #Operator is None (the val_unit holds a single col_unit as operand_1)
        return operand_equal(g_operand1, p_operand1) 

# ---------- condition equality helpers ----------
def equal_commutative_conditions(gold_cond: CondUnit, pred_cond: CondUnit):
    # Order of operands doesn’t matter
    return (
        operand_equal(gold_cond.operand, pred_cond.operand)
        and operand_equal(gold_cond.val1, pred_cond.val1)
    ) or (
        operand_equal(gold_cond.operand, pred_cond.val1)
        and operand_equal(gold_cond.val1, pred_cond.operand)
    )

def equal_in_conditions(gold_cond, pred_cond):
    g_val, p_val = gold_cond.val1, pred_cond.val1
    if isinstance(g_val, list) and isinstance(p_val, list):
        return operand_equal(gold_cond.operand, pred_cond.operand) and set(g_val) == set(p_val)
    return operand_equal(gold_cond.operand, pred_cond.operand) and operand_equal(g_val, p_val)

def opposing_comparison_signs(signs: tuple[str]):
    """Return True if the two operators are logical opposites."""
    gold_op, pred_op = signs
    return OPPOSING_SIGNS.get(gold_op) == pred_op

def equal_atomic_conditions(gold_cond, pred_cond):
    if getattr(gold_cond, "not_op", False) != getattr(pred_cond, "not_op", False):
        return False

    gold_op = getattr(gold_cond, "op_id", None)
    pred_op = getattr(pred_cond, "op_id", None)

    if gold_op == pred_op:
        if gold_op in COMMUTATIVE_OPS:
            return equal_commutative_conditions(gold_cond, pred_cond)
        if gold_op == 'in':
            return equal_in_conditions(gold_cond, pred_cond)
        # generic ordered comparison
        return operand_equal(gold_cond.operand, pred_cond.operand) and \
               operand_equal(gold_cond.val1, pred_cond.val1) and \
               operand_equal(getattr(gold_cond, "val2", None), getattr(pred_cond, "val2", None))

    # allow equivalent comparisons like a < b  vs  b > a
    if opposing_comparison_signs((gold_op, pred_op)):
        return operand_equal(gold_cond.operand, pred_cond.val1) and operand_equal(gold_cond.val1, pred_cond.operand)
    
    return False

# ---------- table equality ----------
def equal_table_units(gold: Any, pred: Any, include_join: bool = True) -> bool:
    if getattr(gold, "table_type", None) != getattr(pred, "table_type", None):
        return False
    if include_join and getattr(gold, "join_type", None) != getattr(pred, "join_type", None):
        return False
    return operand_equal(getattr(gold, "table", None), getattr(pred, "table", None))

# ---------- high-level clause calculators (return dict or None) ----------
def get_limit_score(gold_limit, pred_limit):
    if gold_limit is None and pred_limit is None:
        return None
    if gold_limit is None or pred_limit is None:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    match = 1 if gold_limit == pred_limit else 0
    # treat as single-element comparison (pred_total=1, gold_total=1)
    return safe_prf1(match, 1, 1)

def calc_select_score(gold_select_vals: list, pred_select_vals: list):
    full_matches, gold_len, pred_len = unordered_structural_match(gold_select_vals, pred_select_vals, equal_val_units)

    gold_col_units = [u for unit in gold_select_vals for u in extract_all_col_units(unit)]
    pred_col_units = [u for unit in pred_select_vals for u in extract_all_col_units(unit)]

    gold_cols_noagg = Counter((c.col_id, getattr(c, "isDistinct", False)) for c in gold_col_units)
    pred_cols_noagg = Counter((c.col_id, getattr(c, "isDistinct", False)) for c in pred_col_units)
    matches_noagg = sum(min(gold_cols_noagg[k], pred_cols_noagg.get(k, 0)) for k in gold_cols_noagg)

    gold_cols_nodist = Counter(c.col_id for c in gold_col_units)
    pred_cols_nodist = Counter(c.col_id for c in pred_col_units)
    matches_nodist = sum(min(gold_cols_nodist[k], pred_cols_nodist.get(k, 0)) for k in gold_cols_nodist)

    return {
        "select": safe_prf1(full_matches, gold_len, pred_len),
        "col_no_agg": safe_prf1(matches_noagg, len(gold_col_units), len(pred_col_units)),
        "col_no_distinct": safe_prf1(matches_nodist, len(gold_col_units), len(pred_col_units)),
    }

def calc_from_score(gold_tables: list, pred_tables: list):
    full_matches, gold_len, pred_len = unordered_structural_match(gold_tables, pred_tables, equal_table_units)

    # Table-only ignoring join type
    def table_type_only(t): 
        return TableUnit(getattr(t, "table_type", None), getattr(t, "table", None))
    
    table_matches, _, _ = unordered_structural_match([table_type_only(t) for t in gold_tables],
                                                    [table_type_only(t) for t in pred_tables],
                                                    lambda g, p: equal_table_units(g, p, include_join=False))
    return {
        "from": safe_prf1(full_matches, gold_len, pred_len),
        "table_only": safe_prf1(table_matches, gold_len, pred_len),
    }

def calc_group_by_score(gold_col_units: list, pred_col_units: list):
    if not gold_col_units and not pred_col_units:
        return None
    if not gold_col_units or not pred_col_units:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    matches = len(set(gold_col_units) & set(pred_col_units))
    return safe_prf1(matches, len(gold_col_units), len(pred_col_units))


def calc_order_by_score(gold_list: list, pred_list: list):
    if not gold_list and not pred_list:
        return None
    if not gold_list or not pred_list:
        return {
            "order_by": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "expressions_no_direction": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
        }
    full_matches, num_gold_orders, num_pred_orders = ordered_structural_match(gold_list, pred_list, equal_val_units)
    # undirected expression match (ignore direction)
    undirected_matches, _, _ = unordered_structural_match([v for v, _ in gold_list], [v for v, _ in pred_list], equal_val_units)
    return {
        "order_by": safe_prf1(full_matches, num_gold_orders, num_pred_orders),
        "expressions_no_direction": safe_prf1(undirected_matches, num_gold_orders, num_pred_orders),
    }

def calc_condition_score(gold_condition: list, pred_condition: list):
    if not gold_condition and not pred_condition:
        return None
    if not gold_condition or not pred_condition:
        return {
            "conditions": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "col_only": {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        }

    gold_atomic = [c for c in gold_condition if not isinstance(c, str)]
    pred_atomic = [c for c in pred_condition if not isinstance(c, str)]

    cond_matches, num_gold_conds, num_pred_conds = unordered_structural_match(gold_atomic, pred_atomic, equal_atomic_conditions)

    gold_cols = [cu.col_id for cond in gold_atomic for u in (cond.operand, getattr(cond, "val1", None)) for cu in extract_all_col_units(u)]
    pred_cols = [cu.col_id for cond in pred_atomic for u in (cond.operand, getattr(cond, "val1", None)) for cu in extract_all_col_units(u)]
    gold_col_freqs = Counter(gold_cols)
    pred_col_freqs = Counter(pred_cols)
    col_matches = sum(min(gold_col_freqs[k], pred_col_freqs.get(k, 0)) for k in gold_col_freqs)

    return {
        "conditions": safe_prf1(cond_matches, num_gold_conds, num_pred_conds),
        "col_only": safe_prf1(col_matches, len(gold_cols), len(pred_cols))
    }

# ---------- SQL dict equality (uses f1 only) ----------
def equal_sql_dict(gold_sql: dict, pred_sql: dict) -> bool:
    """Return True only if every component's F1 == 1 (or component is None)."""
    scores = compare_sql_components(gold_sql, pred_sql)

    def all_f1_ones(obj):
        if obj is None:
            return True
        if isinstance(obj, dict):
            # leaf PRF1 dict: check f1 if keys present
            if set(obj.keys()) >= {"precision", "recall", "f1"}:
                return obj.get("f1", 0) == 1
            # otherwise recursively inspect nested dicts
            return all(all_f1_ones(v) for v in obj.values())
        return False

    return all_f1_ones(scores)

# ---------- top-level SQL comparator (returns PRF dicts for each clause) ----------
def compare_sql_components(gold_sql: dict, pred_sql: dict):
    scores = {}
    # Handle set/op constructs (INTERSECT/EXCEPT/UNION) by walking left/right.
    left_gold, left_pred = gold_sql, pred_sql
    for iue_part in SQL_OPS:
        if gold_sql.get(iue_part) or pred_sql.get(iue_part):
            if gold_sql.get(iue_part) and pred_sql.get(iue_part):
                right_equal = equal_sql_dict(gold_sql['right_query'], pred_sql['right_query'])
                scores[iue_part] = {"precision": 1.0 if right_equal else 0.0,
                                    "recall": 1.0 if right_equal else 0.0,
                                    "f1": 1.0 if right_equal else 0.0}
                left_gold = left_gold['left_query']
                left_pred = left_pred['left_query']
            else:
                # one has union/intersect/except, the other doesn’t -> structural mismatch
                return handle_set_op_mismatch()

    # --- now left_gold/left_pred represent the core SELECT/FROM/WHERE/... SQL dicts
    gold_distinct, gold_select = left_gold['select']
    pred_distinct, pred_select = left_pred['select']
    select_scores = calc_select_score(gold_select, pred_select)
    # distinct handled as exact match (1/1/1) or zero
    distinct_match = 1 if gold_distinct == pred_distinct else 0
    select_scores['distinct'] = {"precision": float(distinct_match), "recall": float(distinct_match), "f1": float(distinct_match)}
    scores['select'] = select_scores

    # FROM / explicit join conds
    scores['from'] = calc_from_score(left_gold['from']['table_units'], left_pred['from']['table_units'])
    scores['explicit_join_conds'] = calc_condition_score(left_gold['from'].get('conds', []), left_pred['from'].get('conds', []))

    # WHERE
    scores['where'] = calc_condition_score(left_gold.get('where', []), left_pred.get('where', []))

    # GROUP BY / HAVING
    group_score = calc_group_by_score(left_gold.get('group_by', []), left_pred.get('group_by', []))
    having_score = calc_condition_score(left_gold.get('having', []), left_pred.get('having', []))
    scores['group'] = group_score
    # combine group+having: average p/r/f if both present, else None/one-sided behavior preserved
    if group_score and having_score:
        avg_p = (group_score['precision'] + having_score['conditions']['precision']) / 2
        avg_r = (group_score['recall'] + having_score['conditions']['recall']) / 2
        avg_f = (group_score['f1'] + having_score['conditions']['f1']) / 2
        scores['group_by_having'] = {"precision": avg_p, "recall": avg_r, "f1": avg_f}
    else:
        scores['group_by_having'] = None

    # ORDER BY
    scores['order'] = calc_order_by_score(left_gold.get('order_by', []), left_pred.get('order_by', []))

    # LIMIT
    scores['limit'] = get_limit_score(left_gold.get('limit', None), left_pred.get('limit', None))

    return scores

def handle_set_op_mismatch():
    """
    Create a zero-filled score dictionary when queries
    differ in set-ops (UNION/INTERSECT/EXCEPT).
    """
    return {key: 0 for key in score_keys}

def evaluate_dataset(dataset: str, output_file: str, parsing_errors_log_file, schemas):
    all_scores = []
    all_scores_str = []
    counts, questions, gold_parsed, pred_parsed = run_parser_on_dataset(dataset, '', schemas)
    with open(parsing_errors_log_file, 'w') as error_f:
        json.dump(counts, error_f)
    i = 0
    for g_parsed, p_parsed in zip(gold_parsed, pred_parsed):
        scores = compare_sql_components(g_parsed, p_parsed)
        all_scores.append(scores)
        all_scores_str.append(json.dumps(scores))
        #print(questions[i])
        i += 1
        
    df = pd.DataFrame({'Question' : questions, 'Scores' : all_scores_str})
    df.to_csv(output_file)
    return all_scores



if __name__ == '__main__':

    schemas = deserialize_db_schema_model('data/spider/interim_db_schemas_object')
    all_scores = evaluate_dataset('combined.csv', 'partial_scores.csv', schemas)

    # gold_sql = {'intersect': False, 'union': False, 'except': False, 'from': {'table_units': [TableUnit(table_type='table_unit', table=1, join_type=None)], 'conds': []}, 'select': (False, [ValUnit(unit_op='none', operand1=ColUnit(agg_id='count', col_id=-1, isDistinct=False), operand2=None)]), 'where': None, 'having': None, 'group_by': None, 'order_by': None, 'limit': None}
    # pred_sql = {'intersect': False, 'union': False, 'except': False, 'from': {'table_units': [TableUnit(table_type='table_unit', table=1, join_type=None)], 'conds': []}, 'select': (False, [ValUnit(unit_op='none', operand1=ColUnit(agg_id='count', col_id=7, isDistinct=False), operand2=None)]), 'where': None, 'having': None, 'group_by': None, 'order_by': None, 'limit': None}

    # scores = compare_sql_components(gold_sql, pred_sql)
    # pprint.pprint(scores, indent=4, width=80)
    # print(scores['select'])
    # print(scores['from'])
    # print(scores['where'])
    # print(scores['explicit_join_conds'])
    # print(scores['group'])
    # print(scores['order'])