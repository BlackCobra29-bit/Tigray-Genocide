from django.db.models import Q
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import conditional_escape, format_html, urlize

from .models import Photo_archive


MAX_PHOTO_ARCHIVE_TABLE_PAGE_SIZE = 100

PHOTO_ARCHIVE_ORDER_FIELDS = {
    1: "author__last_name",
    2: "location",
    3: "date_of_event",
    4: "description",
    5: "date_created",
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


def _base_photo_archive_queryset():
    return Photo_archive.objects.select_related("author").only(
        "id",
        "author__first_name",
        "author__last_name",
        "author__username",
        "location",
        "date_of_event",
        "description",
        "date_created",
    )


def _search_photo_archive_queryset(queryset, search):
    if not search:
        return queryset

    return queryset.filter(
        Q(location__icontains=search)
        | Q(description__icontains=search)
        | Q(author__first_name__icontains=search)
        | Q(author__last_name__icontains=search)
        | Q(author__username__icontains=search)
    )


def _ordered_photo_archive_queryset(queryset, params):
    order_column = _bounded_int(params.get("order[0][column]"), 5)
    direction = "-" if params.get("order[0][dir]") == "desc" else ""
    order_field = PHOTO_ARCHIVE_ORDER_FIELDS.get(order_column)

    if order_field:
        return queryset.order_by(
            f"{direction}{order_field}",
            "-date_created",
        )

    return queryset.order_by("-date_created")


def _photo_archive_action(photo_archive):
    archive_label = photo_archive.location or "Photo archive"

    return format_html(
        '<a href="{}" data-toggle="tooltip" data-placement="top" '
        'title="Update Item"><i class="bi bi-pencil-fill"></i></a>'
        "&nbsp; "
        '<a href="#" class="photo-archive-delete-trigger" '
        'data-delete-url="{}" data-delete-title="{}" '
        'data-toggle="tooltip" data-placement="top" '
        'title="Delete Item" aria-label="Delete {}">'
        '<i class="bi bi-trash"></i></a>',
        reverse("update-photo-archive", args=[photo_archive.id]),
        reverse("delete-photo-archive", args=[photo_archive.id]),
        archive_label,
        archive_label,
    )


def _photo_archive_row(photo_archive):
    if photo_archive.author:
        author_name = " ".join(
            part
            for part in (
                photo_archive.author.first_name,
                photo_archive.author.last_name,
            )
            if part
        ) or photo_archive.author.username
    else:
        author_name = "Unknown"

    location = (
        conditional_escape(photo_archive.location)
        if photo_archive.location
        else format_html("<i>{}</i>", "Unknown")
    )
    date_of_event = (
        date_format(photo_archive.date_of_event, "d-M-Y")
        if photo_archive.date_of_event
        else format_html("<i>{}</i>", "Undated")
    )

    return [
        _photo_archive_action(photo_archive),
        conditional_escape(author_name),
        location,
        date_of_event,
        urlize(
            photo_archive.description or "",
            nofollow=True,
            autoescape=True,
        ),
        date_format(photo_archive.date_created, "F d, Y"),
    ]


def build_photo_archive_management_payload(request):
    draw = _bounded_int(request.GET.get("draw"), 0)
    start = _bounded_int(request.GET.get("start"), 0)
    length = _bounded_int(
        request.GET.get("length"),
        10,
        minimum=1,
        maximum=MAX_PHOTO_ARCHIVE_TABLE_PAGE_SIZE,
    )
    search = request.GET.get("search[value]", "").strip()

    base_queryset = _base_photo_archive_queryset()
    records_total = base_queryset.count()
    filtered_queryset = _search_photo_archive_queryset(
        base_queryset,
        search,
    )
    records_filtered = (
        records_total if not search else filtered_queryset.count()
    )
    photo_archives = _ordered_photo_archive_queryset(
        filtered_queryset,
        request.GET,
    )[start : start + length]

    return {
        "draw": draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": [
            _photo_archive_row(photo_archive)
            for photo_archive in photo_archives
        ],
    }
