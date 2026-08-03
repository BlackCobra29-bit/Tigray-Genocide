from django.db.models import Q
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import conditional_escape, format_html, format_html_join, urlize
from django.utils.safestring import mark_safe

from .models import Civilian_victims, Unverified_civilian
from .templatetags.custom import extract_and_join_urls


MAX_TABLE_PAGE_SIZE = 100
UNKNOWN_CELL = mark_safe("<i>Unknown</i>")
UNDATED_CELL = mark_safe("<i>Undated</i>")

SUPERUSER_ORDER_FIELDS = {
    1: "full_name",
    2: "gender",
    3: "age",
    4: "perpetrator",
    5: "place_of_killing",
    6: "woreda__woreda_name",
    7: "source",
    8: "source_link",
    9: "date_of_event",
    10: "remark",
    11: "picture",
    12: "date_created",
}

ADMIN_ORDER_FIELDS = {
    1: "approval",
    2: "full_name",
    3: "gender",
    4: "age",
    5: "perpetrator",
    6: "place_of_killing",
    7: "zone",
    8: "source",
    9: "date_of_event",
    10: "remark",
    11: "picture",
    12: "date_created",
}

UNVERIFIED_ORDER_FIELDS = {
    1: "location",
    2: "number_of_civilian",
    3: "perpetrator",
    4: "woreda__woreda_name",
    5: "source",
    6: "source_link",
    7: "remark",
    8: "date_created",
}


def _bounded_int(value, default, minimum=0, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _base_queryset(user):
    queryset = Civilian_victims.objects.select_related("woreda").only(
        "id",
        "author_id",
        "full_name",
        "gender",
        "age",
        "place_of_killing",
        "woreda",
        "woreda__woreda_name",
        "zone",
        "source",
        "source_link",
        "perpetrator",
        "date_of_event",
        "remark",
        "picture",
        "approval",
        "date_created",
    )
    if user.is_superuser:
        return queryset.filter(approval=True)
    return queryset.filter(author=user)


def _search_queryset(queryset, search, include_status):
    if not search:
        return queryset

    filters = (
        Q(full_name__icontains=search)
        | Q(gender__icontains=search)
        | Q(place_of_killing__icontains=search)
        | Q(woreda__woreda_name__icontains=search)
        | Q(zone__icontains=search)
        | Q(source__icontains=search)
        | Q(source_link__icontains=search)
        | Q(perpetrator__icontains=search)
        | Q(remark__icontains=search)
    )
    if search.isdigit():
        filters |= Q(age=int(search))

    normalized = search.casefold()
    if normalized and normalized in "unknown":
        filters |= (
            Q(age__isnull=True)
            | Q(place_of_killing__isnull=True)
            | Q(source__isnull=True)
            | Q(source_link__isnull=True)
            | Q(remark__isnull=True)
        )
    if normalized and normalized in "undated":
        filters |= Q(date_of_event__isnull=True)
    if include_status:
        if normalized and normalized in "approved":
            filters |= Q(approval=True)
        if normalized and normalized in "pending":
            filters |= Q(approval=False)

    return queryset.filter(filters)


def _format_source(victim):
    source = victim.source
    source_link = victim.source_link or ""
    if not source:
        return UNKNOWN_CELL
    if not source_link or str(urlize(source_link, autoescape=True)) == source_link:
        return conditional_escape(source)

    if "," in source and "," in source_link:
        source_items = source.split(", ")
        link_items = source_link.split(", ")
        rendered_items = []
        for source_item, link_item in zip(source_items, link_items):
            if str(urlize(link_item, autoescape=True)) == link_item:
                rendered_items.append(conditional_escape(source_item))
            else:
                rendered_items.append(
                    format_html(
                        '<a href="{}" id="source_link" target="_blank">'
                        '<i class="fa fa-link"></i> {}</a>',
                        link_item,
                        source_item,
                    )
                )
        return format_html_join(", ", "{}", ((item,) for item in rendered_items))

    return format_html(
        '<a href="{}" id="source_link" target="_blank">'
        '<i class="fa fa-link"></i> {}</a>',
        extract_and_join_urls(source_link),
        source,
    )


def _format_common_cells(victim):
    age = str(victim.age) if victim.age is not None else UNKNOWN_CELL
    place = (
        conditional_escape(victim.place_of_killing)
        if victim.place_of_killing
        else UNKNOWN_CELL
    )
    source_link = (
        conditional_escape(victim.source_link)
        if victim.source_link
        else UNKNOWN_CELL
    )
    event_date = (
        date_format(victim.date_of_event, "d-M-Y")
        if victim.date_of_event
        else UNDATED_CELL
    )
    remark = (
        urlize(victim.remark, autoescape=True)
        if victim.remark
        else UNKNOWN_CELL
    )
    try:
        picture_url = victim.picture.url
    except ValueError:
        picture = UNKNOWN_CELL
    else:
        picture = format_html(
            '<a href="{}" target="_blank">Open in new tab</a>',
            picture_url,
        )

    return {
        "age": age,
        "place": place,
        "source": _format_source(victim),
        "source_link": source_link,
        "event_date": event_date,
        "remark": remark,
        "picture": picture,
        "created": date_format(victim.date_created, "F d, Y"),
    }


def _superuser_row(victim):
    common = _format_common_cells(victim)
    action = format_html(
        '<a href="{}" data-toggle="tooltip" data-placement="top" '
        'title="Update Item"><i class="bi bi-pencil-fill"></i></a>'
        "&nbsp; "
        '<a href="#" class="civilian-delete-trigger admin-delete-trigger" '
        'data-delete-url="{}" data-delete-name="{}" data-delete-label="{}" '
        'data-toggle="tooltip" data-placement="top" '
        'title="Delete Item" aria-label="Delete {}">'
        '<i class="bi bi-trash"></i></a>',
        reverse("update-civilian-victim", args=[victim.id]),
        reverse("delete-civilian-victim", args=[victim.id]),
        victim.full_name,
        victim.full_name,
        victim.full_name,
    )
    return [
        action,
        conditional_escape(victim.full_name.title()),
        conditional_escape(victim.gender),
        common["age"],
        conditional_escape(victim.perpetrator),
        common["place"],
        conditional_escape(str(victim.woreda)) if victim.woreda else UNKNOWN_CELL,
        common["source"],
        common["source_link"],
        common["event_date"],
        common["remark"],
        common["picture"],
        common["created"],
    ]


def _administrator_row(victim):
    common = _format_common_cells(victim)
    action = format_html(
        '<a href="{}" data-toggle="tooltip" data-placement="top" '
        'title="Update Item"><i class="bi bi-pencil-fill"></i></a>',
        reverse("update-civilian-victim", args=[victim.id]),
    )
    status = (
        mark_safe('<span class="badge bg-green">Approved</span>')
        if victim.approval
        else mark_safe('<span class="badge bg-red">Pending</span>')
    )
    return [
        action,
        status,
        conditional_escape(victim.full_name),
        conditional_escape(victim.gender),
        common["age"],
        conditional_escape(victim.perpetrator),
        common["place"],
        conditional_escape(victim.zone),
        common["source"],
        common["event_date"],
        common["remark"],
        common["picture"],
        common["created"],
    ]


def get_filtered_ordered_civilian_queryset(user, params):
    search = params.get("search[value]", "").strip()
    queryset = _search_queryset(
        _base_queryset(user),
        search,
        include_status=not user.is_superuser,
    )

    order_fields = (
        SUPERUSER_ORDER_FIELDS
        if user.is_superuser
        else ADMIN_ORDER_FIELDS
    )
    order_column = _bounded_int(params.get("order[0][column]"), 0)
    order_field = order_fields.get(order_column)
    if order_field:
        if params.get("order[0][dir]") == "desc":
            order_field = f"-{order_field}"
        return queryset.order_by(order_field, "-date_created")

    return queryset.order_by("-date_created")


def build_civilian_management_payload(request):
    draw = _bounded_int(request.GET.get("draw"), 0)
    start = _bounded_int(request.GET.get("start"), 0)
    length = _bounded_int(
        request.GET.get("length"),
        10,
        minimum=1,
        maximum=MAX_TABLE_PAGE_SIZE,
    )
    search = request.GET.get("search[value]", "").strip()

    queryset = _base_queryset(request.user)
    records_total = queryset.count()
    filtered_queryset = get_filtered_ordered_civilian_queryset(
        request.user,
        request.GET,
    )
    records_filtered = (
        records_total if not search else filtered_queryset.count()
    )

    victims = filtered_queryset[start : start + length]
    row_builder = _superuser_row if request.user.is_superuser else _administrator_row

    return {
        "draw": draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": [row_builder(victim) for victim in victims],
    }


def _base_unverified_queryset():
    return Unverified_civilian.objects.select_related("woreda").only(
        "id",
        "location",
        "number_of_civilian",
        "perpetrator",
        "woreda",
        "woreda__woreda_name",
        "source",
        "source_link",
        "remark",
        "date_created",
    )


def _search_unverified_queryset(queryset, search):
    if not search:
        return queryset

    filters = (
        Q(location__icontains=search)
        | Q(perpetrator__icontains=search)
        | Q(woreda__woreda_name__icontains=search)
        | Q(source__icontains=search)
        | Q(source_link__icontains=search)
        | Q(remark__icontains=search)
    )
    if search.isdigit():
        filters |= Q(number_of_civilian=int(search))

    normalized = search.casefold()
    if normalized and normalized in "unknown":
        filters |= Q(source__isnull=True) | Q(remark__isnull=True)

    return queryset.filter(filters)


def _unverified_row(victim):
    action = format_html(
        '<a href="{}" data-toggle="tooltip" data-placement="top" '
        'title="Update Item"><i class="bi bi-pencil-fill"></i></a>'
        "&nbsp; "
        '<a href="#" class="unverified-delete-trigger admin-delete-trigger" '
        'data-delete-url="{}" data-delete-name="{}" data-delete-label="{}" '
        'data-toggle="tooltip" data-placement="top" '
        'title="Delete Item" aria-label="Delete {}">'
        '<i class="bi bi-trash"></i></a>',
        reverse("update-unverified-civilian-victim", args=[victim.id]),
        reverse("delete-unverified-civilian-victim", args=[victim.id]),
        victim.location,
        victim.location,
        victim.location,
    )
    remark = (
        urlize(victim.remark, autoescape=True)
        if victim.remark
        else UNKNOWN_CELL
    )

    return [
        action,
        conditional_escape(victim.location),
        str(victim.number_of_civilian),
        conditional_escape(victim.perpetrator),
        (
            conditional_escape(str(victim.woreda))
            if victim.woreda
            else conditional_escape(None)
        ),
        _format_source(victim),
        conditional_escape(victim.source_link),
        remark,
        date_format(victim.date_created, "F d, Y"),
    ]


def get_filtered_ordered_unverified_queryset(params):
    search = params.get("search[value]", "").strip()
    queryset = _search_unverified_queryset(
        _base_unverified_queryset(),
        search,
    )

    order_column = _bounded_int(params.get("order[0][column]"), 0)
    order_field = UNVERIFIED_ORDER_FIELDS.get(order_column)
    if order_field:
        if params.get("order[0][dir]") == "desc":
            order_field = f"-{order_field}"
        return queryset.order_by(order_field, "-date_created")

    return queryset.order_by("-date_created")


def build_unverified_management_payload(request):
    draw = _bounded_int(request.GET.get("draw"), 0)
    start = _bounded_int(request.GET.get("start"), 0)
    length = _bounded_int(
        request.GET.get("length"),
        10,
        minimum=1,
        maximum=MAX_TABLE_PAGE_SIZE,
    )
    search = request.GET.get("search[value]", "").strip()

    records_total = _base_unverified_queryset().count()
    filtered_queryset = get_filtered_ordered_unverified_queryset(request.GET)
    records_filtered = (
        records_total if not search else filtered_queryset.count()
    )
    victims = filtered_queryset[start : start + length]

    return {
        "draw": draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": [_unverified_row(victim) for victim in victims],
    }


def build_unverified_export_payload(params):
    queryset = get_filtered_ordered_unverified_queryset(params)
    rows = []
    for index, victim in enumerate(
        queryset.iterator(chunk_size=500),
        start=1,
    ):
        rows.append(
            [
                index,
                str(victim.location),
                victim.number_of_civilian,
                str(victim.perpetrator),
                str(victim.woreda),
                str(victim.source),
                str(victim.source_link),
                str(victim.remark) if victim.remark else "Unknown",
            ]
        )

    return {
        "recordsFiltered": len(rows),
        "data": rows,
    }
