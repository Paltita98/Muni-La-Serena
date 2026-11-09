from datetime import datetime, time, timedelta

from django.utils import timezone


def filter_by_local_dates(queryset, field_name, date_from=None, date_to=None):
    local_timezone = timezone.get_current_timezone()
    if date_from:
        start = timezone.make_aware(datetime.combine(date_from, time.min), local_timezone)
        queryset = queryset.filter(**{f'{field_name}__gte': start})
    if date_to:
        day_after = date_to + timedelta(days=1)
        end = timezone.make_aware(datetime.combine(day_after, time.min), local_timezone)
        queryset = queryset.filter(**{f'{field_name}__lt': end})
    return queryset