from django import template


register = template.Library()


@register.filter(name='exist')
def another_table_exist(d, index):
    return bool(d[int(not index)])
