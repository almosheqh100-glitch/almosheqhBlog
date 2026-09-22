"""Stable category ordering; counts come from category data."""
import html
CATEGORY_ORDER = ["المقالات", "البرامج", "تطبيقات Android", "تطبيقات windos", "تطبيقات الآيفون"]

def ordered_categories(categories):
    order = {name: index for index, name in enumerate(CATEGORY_ORDER)}
    return sorted(categories, key=lambda c: (order.get(c["name"], len(order)), c["name"]))

def category_label(category):
    return f"{html.unescape(category['name'])} ({int(category.get('post_count', 0))})"
