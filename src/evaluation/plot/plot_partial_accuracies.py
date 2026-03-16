import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os

feature_groups = {
    "FROM": ["from-full", "from-table_only"],
    "SELECT": ["select-select", "select-col_no_agg", "select-col_no_distinct", "select-distinct"],
    "WHERE": ["where-conditions", "where-col_only"],
    "JOIN": ["explicit_join_conds-col_only", "explicit_join_conds-conditions"],
    "GROUP": ["group", "group_by_having"],
    "LIMIT": ["limit"],
    "ORDER": ["order-order_by", "order-expressions_no_direction"]
}

feature_name_map = {
    "from-full": "Full",
    "from-table_only": "Table Only",
    "select-select": "Select",
    "select-col_no_agg": "Col No Agg",
    "select-col_no_distinct": "Col No Distinct",
    "select-distinct": "Distinct",
    "where-conditions": "Conditions",
    "where-col_only": "Col Only",
    "explicit_join_conds-col_only": "Col Only",
    "explicit_join_conds-conditions": "Conditions",
    "group": "GROUP",
    "limit": "LIMIT",
    "order-order_by": "Order By",
    "order-expressions_no_direction": "Expr No Dir",
    "group_by_having": "GROUP BY + HAVING"
}

# Combine scores into a DataFrame with group info
def prepare_dataframe(f1_scores, precision_scores, recall_scores):
    data = []
    for group, features in feature_groups.items():
        for f in features:
            data.append({
                "Group": group,
                "Feature": feature_name_map.get(f, f),
                "F1": f1_scores.get(f, 0),
                "Precision": precision_scores.get(f, 0),
                "Recall": recall_scores.get(f, 0)
            })
    return pd.DataFrame(data)

# Function to plot one metric at a time
def plot_metric(df, metric, output_dir):
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df, x="Feature", y=metric, hue="Group", dodge=False)
    plt.title(f"{metric} Scores by Feature Group")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel(f"{metric} Score")
    plt.xlabel("Feature Subcategory")
    plt.legend(title="Group")
    plt.tight_layout()
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)  # ensure directory exists
        output_path = os.path.join(output_dir, f"{metric}_scores.png")
        plt.savefig(output_path, dpi=300)
    plt.show()

def plot(averaged_f1_scores, averaged_precision_scores, averaged_recall_scores, output_dir):
    df_scores = prepare_dataframe(averaged_f1_scores, averaged_precision_scores, averaged_recall_scores)
    # Plot F1, Precision, and Recall separately
    plot_metric(df_scores, "F1", output_dir)
    plot_metric(df_scores, "Precision", output_dir)
    plot_metric(df_scores, "Recall", output_dir)
