class Table:
    """
    Represents a database table, storing its name, columns, and primary key.

    This class acts as a consistent intermediate data model for table schema
    information extracted from various Text-to-SQL datasets.
    """
    def __init__(self, name: str):
        self.name = name
        self.primary_key = None
        self.attributes = {}
    
    def set_primary_key(self, p_key_name):
        self.primary_key = p_key_name

    def add_attribute(self, column_name: str, column_type: str):
        self.attributes[column_name] = column_type
    

class DBSchemaModel:
    """
    Object representing the schema of a db_id in the dataset.

    This class acts as a consistent intermediate data model for database schema
    information extracted from various Text-to-SQL datasets.
    """
    def __init__(self):
        self.tables = []
        self.foreign_keys = {}
    
    def add_table(self, table : Table):
        self.tables.append(table)

    def get_ddl_string(self):
        ddl_statements = []

        #CREATE TABLE statements
        for table in self.tables:
            cols = []
            for attr, typ in table.attributes.items():
                sql_type = self._map_type(typ)
                cols.append(f"{attr} {sql_type}")
            if table.primary_key:
                cols.append(f"PRIMARY KEY ({table.primary_key})")
            col_string = ", ".join(cols)
            ddl_statements.append(f"CREATE TABLE {table.name} ({col_string});")

        #FOREIGN KEY constraints
        for (src_table, src_col), (tgt_table, tgt_col) in self.foreign_keys.items():
            ddl_statements.append(
                f"FOREIGN KEY ({src_table}.{src_col}) REFERENCES {tgt_table} ({tgt_col});"
            )

        return "\n".join(ddl_statements)

    def _map_type(self, internal_type):
        """Map internal type representation to SQL type."""
        internal_type = internal_type.lower()
        if internal_type == "text":
            return "TEXT"
        elif internal_type == "number":
            return "INTEGER"
        else:
            return "OTHERS"  

    def __str__(self):
        result = []
        for table in self.tables:
            result.append(f"Table: {table.name}")
            result.append(f"  Primary Key: {table.primary_key}")
            result.append("  Attributes:")
            for attr, typ in table.attributes.items():
                result.append(f"    - {attr} ({typ})")
        if self.foreign_keys:
            result.append("Foreign Keys:")
            for (src_table, src_col), (tgt_table, tgt_col) in self.foreign_keys.items():
                result.append(f"  - {src_table}.{src_col} → {tgt_table}.{tgt_col}")
        return "\n".join(result)

    def get_db_schema_complexity(self):
        """Returns the total number of attributes of all tables in schema, and num FKeys"""
        totalNumAttributes = 0
        for table in self.tables:
            totalNumAttributes += len(table.attributes)
        
        return totalNumAttributes, len(self.foreign_keys) #may adjust metric 