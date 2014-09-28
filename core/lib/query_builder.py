__author__ = 'nolka'


def parse_data(data_dict):
    query_conditions = []
    for attr, value in data_dict.iteritems():
        query_conditions.append((attr, _parse(value)))
    return query_conditions

def _parse(value):
    if ":" in value:
        modifier, value = value.split(":", 1)
        if modifier == "like":
            return "LIKE ?", "%"+value+"%"
        if modifier == "<":
            return "< ?", value
        if modifier == ">":
            return "> ?", value
        if modifier == "<=":
            return "<= ?", value
        if modifier == ">=":
            return ">= ?", value
        if modifier == "!=":
            return "<> ?", value
        if modifier == "in":
            return "IN (?)", value
        if modifier == "!in":
            return "NOT IN (?)", value
            # if modifier == "range":
            # vf, vt = value.split('-')
            #     return ""
    else:
        return "=?", value