import os
import sqlite3
import json

def analyze_sqlite_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]

    total_columns = 0
    total_foreign_keys = 0

    for table in tables:
        # Count columns
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = cursor.fetchall()
        total_columns += len(columns)

        # Count foreign keys
        cursor.execute(f"PRAGMA foreign_key_list('{table}')")
        fks = cursor.fetchall()
        total_foreign_keys += len(fks)

    conn.close()

    return {
        "num_tables": len(tables),
        "num_columns": total_columns,
        "num_foreign_keys": total_foreign_keys
    }

def analyze_directory(base_dir, output_path):
    results = {}
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".sqlite"):
                db_path = os.path.join(root, file)
                db_name = os.path.basename(root)  # folder name as ID
                results[db_name] = analyze_sqlite_schema(db_path)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    base_dir = "data/spider/database_files"  
    output_path = "schema_stats.json"
    analyze_directory(base_dir, output_path)
