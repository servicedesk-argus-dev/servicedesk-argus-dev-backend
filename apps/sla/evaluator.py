import operator

OPERATORS = {
    "eq": operator.eq,
    "neq": operator.ne,
    "gt": operator.gt,
    "lt": operator.lt,
    "gte": operator.ge,
    "lte": operator.le,
    "in": lambda f, v: f in v if isinstance(v, (list, tuple)) else f in [v],
    "not_in": lambda f, v: f not in v if isinstance(v, (list, tuple)) else f not in [v],
}

def evaluate_condition(instance, condition_data: dict) -> bool:
    """
    Evaluates a JSON condition against a Django model instance.
    Expected format:
    {
        "condition": "AND",
        "rules": [
            {"field": "state", "operator": "eq", "value": "IN_PROGRESS"},
            {"field": "priority", "operator": "in", "value": ["P1", "P2"]}
        ]
    }
    """
    if not condition_data:
        # Empty condition means it doesn't match
        return False
        
    logical_op = condition_data.get("condition", "AND").upper()
    rules = condition_data.get("rules", [])
    
    if not rules:
        return False
        
    results = []
    for rule in rules:
        if "condition" in rule:
            # Nested rule group
            results.append(evaluate_condition(instance, rule))
        else:
            field = rule.get("field")
            op = rule.get("operator", "eq")
            value = rule.get("value")
            
            if not field:
                continue
                
            try:
                # Handle basic dot notation for foreign keys (e.g., 'organization.name')
                parts = field.split('.')
                field_value = instance
                for part in parts:
                    field_value = getattr(field_value, part)
                    if field_value is None:
                        break
                        
                # Normalize choices and model instances
                if hasattr(field_value, 'id'):
                    field_value = str(field_value.id)
            except AttributeError:
                field_value = None
            
            op_func = OPERATORS.get(op, operator.eq)
            try:
                result = op_func(field_value, value)
            except Exception:
                result = False
            results.append(result)
            
    if logical_op == "OR":
        return any(results)
    return all(results)
