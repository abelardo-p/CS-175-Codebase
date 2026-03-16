from collections import defaultdict
from evaluation.process_query import *
from evaluation.structural_evaluate import *

def aggregate_results_by_clause(all_scores):
    aggregate_f1_scores = defaultdict(int)
    aggregate_prec_scores = defaultdict(int)
    aggregate_recall_scores = defaultdict(int)
    clause_counts = {key: 0 for key in score_keys}

    for scores in all_scores:
        # special case: all zero scores (e.g., set-op mismatch)
        if all(val == 0 for val in scores.values()):
            for key in clause_counts:
                clause_counts[key] += 1
            continue

        # --- FROM ---
        aggregate_f1_scores['from-full'] += scores['from']['from']['f1']
        aggregate_f1_scores['from-table_only'] += scores['from']['table_only']['f1']
        aggregate_prec_scores['from-full'] += scores['from']['from']['precision']
        aggregate_prec_scores['from-table_only'] += scores['from']['table_only']['precision']
        aggregate_recall_scores['from-full'] += scores['from']['from']['recall']
        aggregate_recall_scores['from-table_only'] += scores['from']['table_only']['recall']
        clause_counts['from'] += 1

        # --- explicit join conditions ---
        if scores['explicit_join_conds'] is not None:
            clause_counts['explicit_join_conds'] += 1
            aggregate_f1_scores['explicit_join_conds-col_only'] += scores['explicit_join_conds']['col_only']['f1']
            aggregate_f1_scores['explicit_join_conds-conditions'] += scores['explicit_join_conds']['conditions']['f1']
            aggregate_prec_scores['explicit_join_conds-col_only'] += scores['explicit_join_conds']['col_only']['precision']
            aggregate_prec_scores['explicit_join_conds-conditions'] += scores['explicit_join_conds']['conditions']['precision']
            aggregate_recall_scores['explicit_join_conds-col_only'] += scores['explicit_join_conds']['col_only']['recall']
            aggregate_recall_scores['explicit_join_conds-conditions'] += scores['explicit_join_conds']['conditions']['recall']

        # --- GROUP ---
        if scores['group'] is not None:
            clause_counts['group'] += 1
            aggregate_f1_scores['group'] += scores['group']['f1']
            aggregate_prec_scores['group'] += scores['group']['precision']
            aggregate_recall_scores['group'] += scores['group']['recall']

        # --- GROUP BY / HAVING ---
        if scores['group_by_having'] is not None:
            clause_counts['group_by_having'] += 1
            aggregate_f1_scores['group_by_having'] += scores['group_by_having']['f1']
            aggregate_prec_scores['group_by_having'] += scores['group_by_having']['precision']
            aggregate_recall_scores['group_by_having'] += scores['group_by_having']['recall']

        # --- LIMIT ---
        if scores['limit'] is not None:
            clause_counts['limit'] += 1
            aggregate_f1_scores['limit'] += scores['limit']['f1']
            aggregate_prec_scores['limit'] += scores['limit']['precision']
            aggregate_recall_scores['limit'] += scores['limit']['recall']

        # --- ORDER BY ---
        if scores['order'] is not None:
            clause_counts['order'] += 1
            aggregate_f1_scores['order-order_by'] += scores['order']['order_by']['f1']
            aggregate_f1_scores['order-expressions_no_direction'] += scores['order']['expressions_no_direction']['f1']
            aggregate_prec_scores['order-order_by'] += scores['order']['order_by']['precision']
            aggregate_prec_scores['order-expressions_no_direction'] += scores['order']['expressions_no_direction']['precision']
            aggregate_recall_scores['order-order_by'] += scores['order']['order_by']['recall']
            aggregate_recall_scores['order-expressions_no_direction'] += scores['order']['expressions_no_direction']['recall']

        # --- SELECT (always not None) ---
        clause_counts['select'] += 1
        for subkey, metrics in scores['select'].items():
            key_name = f'select-{subkey}'
            aggregate_f1_scores[key_name] += metrics['f1']
            aggregate_prec_scores[key_name] += metrics['precision']
            aggregate_recall_scores[key_name] += metrics['recall']

        # --- WHERE ---
        if scores['where'] is not None:
            clause_counts['where'] += 1
            for subkey, metrics in scores['where'].items():
                key_name = f'where-{subkey}'
                aggregate_f1_scores[key_name] += metrics['f1']
                aggregate_prec_scores[key_name] += metrics['precision']
                aggregate_recall_scores[key_name] += metrics['recall']

    # --- compute averages ---
    averaged_f1 = {}
    averaged_prec = {}
    averaged_recall = {}

    key_to_clause = {
        'from-full': 'from',
        'from-table_only': 'from',
        'explicit_join_conds-col_only': 'explicit_join_conds',
        'explicit_join_conds-conditions': 'explicit_join_conds',
        'group': 'group',
        'group_by_having': 'group_by_having',
        'limit': 'limit',
        'order-order_by': 'order',
        'order-expressions_no_direction': 'order',
        # select subkeys
        **{f'select-{k}': 'select' for k in ['col_no_agg', 'col_no_distinct', 'distinct', 'select']},
        # where subkeys
        **{f'where-{k}': 'where' for k in ['col_only', 'conditions']}
    }

    for key, total in aggregate_f1_scores.items():
        parent = key_to_clause[key]
        count = clause_counts[parent] if clause_counts[parent] > 0 else 1
        averaged_f1[key] = total / count
        averaged_prec[key] = aggregate_prec_scores[key] / count
        averaged_recall[key] = aggregate_recall_scores[key] / count

    return averaged_f1, averaged_prec, averaged_recall


if __name__ == '__main__':

    schemas = deserialize_db_schema_model('data/spider/interim_db_schemas_object')
    all_scores = evaluate_dataset('combined.csv', 'partial_scores.csv', schemas)
    aggregate_f1_scores, aggregate_prec_scores, aggregate_recall_scores = aggregate_results_by_clause(all_scores)
    print(aggregate_f1_scores)
    print(aggregate_prec_scores)
    print(aggregate_recall_scores)