from django.db.models import Q
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import conditional_escape, format_html

from .models import Webinar


MAX_WEBINAR_TABLE_PAGE_SIZE = 100

WEBINAR_ORDER_FIELDS = {
    1: "author__last_name",
    2: "webinar_title",
    3: "webinar_video_url",
    4: "date_created",
}


def _bounded_int(value, default, minimum=0, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _base_webinar_queryset():
    return Webinar.objects.select_related("author").only(
        "id",
        "author__first_name",
        "author__last_name",
        "author__username",
        "webinar_title",
        "webinar_video_url",
        "date_created",
    )


def _search_webinar_queryset(queryset, search):
    if not search:
        return queryset

    return queryset.filter(
        Q(webinar_title__icontains=search)
        | Q(webinar_video_url__icontains=search)
        | Q(author__first_name__icontains=search)
        | Q(author__last_name__icontains=search)
        | Q(author__username__icontains=search)
    )


def _ordered_webinar_queryset(queryset, params):
    order_column = _bounded_int(params.get("order[0][column]"), 4)
    direction = "-" if params.get("order[0][dir]") == "desc" else ""
    order_field = WEBINAR_ORDER_FIELDS.get(order_column)

    if order_field:
        return queryset.order_by(
            f"{direction}{order_field}",
            "-date_created",
        )

    return queryset.order_by("-date_created")


def _webinar_action(webinar):
    return format_html(
        '<a href="{}" data-toggle="tooltip" data-placement="top" '
        'title="Update Item"><i class="bi bi-pencil-fill"></i></a>'
        "&nbsp; "
        '<a href="#" class="webinar-delete-trigger admin-delete-trigger" '
        'data-delete-url="{}" data-delete-title="{}" data-delete-label="{}" '
        'data-toggle="tooltip" data-placement="top" '
        'title="Delete Item" aria-label="Delete {}">'
        '<i class="bi bi-trash"></i></a>',
        reverse("update-webinar-discussion", args=[webinar.id]),
        reverse("delete-webinar-discussion", args=[webinar.id]),
        webinar.webinar_title,
        webinar.webinar_title,
        webinar.webinar_title,
    )


def _webinar_row(webinar):
    if webinar.author:
        author_name = " ".join(
            part
            for part in (
                webinar.author.first_name,
                webinar.author.last_name,
            )
            if part
        ) or webinar.author.username
    else:
        author_name = "Unknown"

    video_link = "None"
    if webinar.webinar_video_url:
        video_link = format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            "Open in new tab</a>",
            webinar.webinar_video_url,
        )

    return [
        _webinar_action(webinar),
        conditional_escape(author_name),
        conditional_escape(webinar.webinar_title),
        video_link,
        date_format(webinar.date_created, "d-M-Y"),
    ]


def build_webinar_management_payload(request):
    draw = _bounded_int(request.GET.get("draw"), 0)
    start = _bounded_int(request.GET.get("start"), 0)
    length = _bounded_int(
        request.GET.get("length"),
        10,
        minimum=1,
        maximum=MAX_WEBINAR_TABLE_PAGE_SIZE,
    )
    search = request.GET.get("search[value]", "").strip()

    base_queryset = _base_webinar_queryset()
    records_total = base_queryset.count()
    filtered_queryset = _search_webinar_queryset(
        base_queryset,
        search,
    )
    records_filtered = (
        records_total if not search else filtered_queryset.count()
    )
    webinars = _ordered_webinar_queryset(
        filtered_queryset,
        request.GET,
    )[start : start + length]

    return {
        "draw": draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": [_webinar_row(webinar) for webinar in webinars],
    }
