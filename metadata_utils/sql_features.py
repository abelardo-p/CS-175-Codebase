from dataclasses import dataclass, field

"""Defines a set of attributes about a query that can be used to categorize its difficulty"""
@dataclass
class SQLFeatures:
    has_subquery:           bool = False
    has_limit:              bool = False
    has_order_by:           bool = False
    num_order_attributes:   int = 0
    query_length:           int = 0
    num_table_aliases:      int = 0
    num_joins:              int = 0

    num_components_1:       int = 0
    num_components_2:       int = 0
    num_agg:                int = 0
    num_select_cols:        int = 0
    num_where_conditions:   int = 0
    num_group_by:           int = 0

    def count_other_components(self):
        return (self.num_agg > 1) + (self.num_select_cols > 1) + (self.num_where_conditions > 1) + (self.num_group_by > 1)
    
    def print_attributes(self):
        for field, value in self.__dict__.items():
            print(f"{field}: {value}")