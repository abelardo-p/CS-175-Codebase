from evaluation.strat_execution_eval import generate_stratified_accuracies
from evaluation.execution_evaluate import execution_errors
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

def output_accuracies(base_dir, total_acc, accuracies):
    accuracies['Total Accuracy'] = pd.DataFrame({"Accuracy" : [total_acc]})
    output_file = os.path.join(base_dir, "all_accuracies.xlsx")
    with pd.ExcelWriter(output_file) as writer:
        for stratified_feature, val in accuracies.items():
            val.to_excel(writer, sheet_name=stratified_feature[:31], index=False)  

def plot(accuracy, base_dir, metadata_csv=None, accuracies_csv=None):
    out_dir = os.path.join(base_dir, 'plots')
    os.makedirs(out_dir, exist_ok=True)
    accuracies, df = generate_stratified_accuracies(metadata_csv, accuracies_csv)
    output_accuracies(base_dir, accuracy, accuracies)

    # Features to plot
    features_info = [
        ("hardness", accuracies["acc_by_hardness"], "Hardness"),
        ("num_joins", accuracies["acc_by_joins"], "Number of Joins"),
        ("num_agg", accuracies["acc_by_aggs"], "Number of Aggregations"),
        ("num_where_conditions", accuracies["acc_by_where"], "Number of WHERE Conditions"),
        ("has_subquery", accuracies["acc_by_subqquery"], "Has Subquery (0=No,1=Yes)"),
        ("query_length_bin", accuracies["acc_by_query_length"], "Query Length (tokens)"),
        ("num_tables_bin", accuracies["acc_by_num_tables"], "Number of Tables (binned)"),
        ("num_columns_bin", accuracies["acc_by_total_schema_cols"], "Total Schema Columns (binned)"),
        ("num_foreign_keys", accuracies["acc_by_num_fkeys"], "Number of Foreign Keys")
    ]

    # Create multi-panel figure
    n_plots = len(features_info)
    n_cols = 3
    n_rows = (n_plots + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 4 * n_rows))
    axes = axes.flatten()

    for i, (feature, acc_values, xlabel) in enumerate(features_info):
        ax = axes[i]

        # Fill NaN with 0 so seaborn keeps alignment
        acc_filled = acc_values.fillna(0)

        acc_plot = sns.barplot(
            x=acc_filled.index.astype(str),
            y=acc_filled.values,
            ax=ax,
            color="tab:blue"
        )
        ax.set_ylabel("Exec Accuracy", color="tab:blue")
        ax.set_xlabel(xlabel)
        ax.set_ylim(0, 1.0)

        # Add accuracy labels
        for patch, (bin_label, val) in zip(acc_plot.patches, acc_values.items()):
            if pd.notna(val):  # show real percentage
                ax.annotate(f"{val:.2%}",
                            (patch.get_x() + patch.get_width() / 2., patch.get_height()),
                            ha="center", va="bottom", fontsize=9, color="blue")
            else:  # optional: leave unlabeled (or show 'N/A')
                # ax.annotate("N/A", (patch.get_x() + patch.get_width() / 2., 0.01),
                #             ha="center", va="bottom", fontsize=9, color="blue")
                pass

        # Counts (right y-axis)
        ax2 = ax.twinx()
        counts = df[feature].value_counts().reindex(acc_values.index, fill_value=0)
        count_plot = sns.barplot(
            x=counts.index.astype(str),
            y=counts.values,
            ax=ax2,
            alpha=0.3,
            color="#363636"
        )
        ax2.set_ylabel("Counts", color="#363636")

        #Add count labels
        for patch, val in zip(count_plot.patches, counts.values):
            ax2.annotate(f"{val}",
                            (patch.get_x() + patch.get_width() / 2., patch.get_height()),
                            ha="center", va="bottom", fontsize=9, color="#363636")


    # Remove empty subplots if any
    for j in range(i+1, len(axes)):
        fig.delaxes(axes[j])

    plt.tight_layout()
    plt.savefig(f"{out_dir}/all_features_accuracy_counts.png")
    plt.show()

    # Plot errors logged while trying to execute the predicted query
    error_counts = df['pred_error'].value_counts().reindex(execution_errors, fill_value=0).reset_index()
    error_counts.columns = ['Error Type', 'Count']

    plt.figure(figsize=(8, 5))
    sns.barplot(
        data=error_counts,
        x='Error Type',
        y='Count',
        order=execution_errors,
        color='steelblue'
    )
    plt.ylabel("Frequency")
    plt.title("Distribution of Prediction Execution Errors")
    plt.xticks(rotation=45)

    # Save as separate file
    plt.tight_layout()
    plt.savefig(f"{out_dir}/execution_error_distribution.png", dpi=300)
    plt.close()


if __name__ == '__main__':
    plot(os.getcwd())