"""
Utility functions for Project Dashboard.
"""

from typing import Any


def group_items_by_key(items: list[dict], key: str, default: str = 'unknown') -> dict[str, list]:
    """
    Group a list of dicts by a key value.

    Args:
        items: List of dictionaries to group
        key: The key to group by
        default: Default value if key is missing

    Returns:
        Dict mapping key values to lists of items
    """
    result = {}
    for item in items:
        k = item.get(key, default)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return result
