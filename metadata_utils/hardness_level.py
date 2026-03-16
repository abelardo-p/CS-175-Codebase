from metadata_utils.sql_features import SQLFeatures

def classify(features: SQLFeatures) -> str:
    """Classifies a sample's hardness given by its set of sql features"""

    count_comp1_ = features.num_components_1
    count_comp2_ = features.num_components_2
    count_others_ = features.count_other_components()

    if count_comp1_ <= 1 and count_comp2_ == 0 and count_others_ == 0:
        return "easy"
    elif (count_others_ <= 2 and count_comp1_ <= 1 and count_comp2_ == 0) or \
        (count_comp1_ <= 2 and count_others_ < 2 and count_comp2_ == 0):
        return "medium"
    elif (count_others_ > 2 and count_comp1_ <= 2 and count_comp2_ == 0) or \
                (2 < count_comp1_ <= 3 and count_others_ <= 2 and count_comp2_ == 0) or \
                (count_comp1_ <= 1 and count_others_ == 0 and count_comp2_ <= 1):
        return "hard"
    else:
        return "extra"

