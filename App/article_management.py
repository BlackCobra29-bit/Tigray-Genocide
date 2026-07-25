from django.db.models import Q
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import conditional_escape, format_html

from .models import Analysis_articles


MAX_ARTICLE_TABLE_PAGE_SIZE = 100

ARTICLE_ORDER_FIELDS = {
    2: "author__last_name",
    3: "title",
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


def _base_article_queryset(user):
    queryset = Analysis_articles.objects.select_related("author").only(
        "id",
        "author__first_name",
        "author__last_name",
        "author__username",
        "title",
        "thumbnail",
        "approval",
        "draft",
        "date_created",
    )

    if user.is_superuser:
        return queryset.filter(
            Q(approval=True, draft=False)
            | Q(author=user, draft=True)
        )

    return queryset.filter(author=user)


def _search_article_queryset(queryset, search):
    if not search:
        return queryset

    filters = (
        Q(title__icontains=search)
        | Q(author__first_name__icontains=search)
        | Q(author__last_name__icontains=search)
        | Q(author__username__icontains=search)
    )

    normalized = search.casefold()
    if normalized in {"draft", "drafts"}:
        filters |= Q(draft=True)
    elif normalized in {"published", "publish"}:
        filters |= Q(draft=False, approval=True)
    elif normalized in {"pending", "pending approval"}:
        filters |= Q(draft=False, approval=False)

    return queryset.filter(filters)


def _ordered_article_queryset(queryset, params):
    order_column = _bounded_int(params.get("order[0][column]"), 5)
    direction = "-" if params.get("order[0][dir]") == "desc" else ""

    if order_column == 1:
        return queryset.order_by(
            f"{direction}draft",
            f"{direction}approval",
            "-date_created",
        )

    order_field = ARTICLE_ORDER_FIELDS.get(order_column)
    if order_field:
        return queryset.order_by(
            f"{direction}{order_field}",
            "-date_created",
        )

    return queryset.order_by("-date_created")


def _article_action(article, user):
    update_name = (
        "update-draft-article"
        if article.draft
        else "update-analysis-article"
    )
    update_title = "Edit draft" if article.draft else "Update article"
    action = format_html(
        '<a href="{}" data-toggle="tooltip" data-placement="top" '
        'title="{}"><i class="bi bi-pencil-fill"></i></a>',
        reverse(update_name, args=[article.id]),
        update_title,
    )

    if user.is_superuser or article.draft:
        action = format_html(
            '{} <a href="{}" data-toggle="tooltip" data-placement="top" '
            'title="Delete article"><i class="bi bi-trash"></i></a>',
            action,
            reverse("delete-analysis-article", args=[article.id]),
        )

    return action


def _article_status(article):
    if article.draft:
        css_class = "article-status--draft"
        label = "Draft"
    elif article.approval:
        css_class = "article-status--published"
        label = "Published"
    else:
        css_class = "article-status--pending"
        label = "Pending approval"

    return format_html(
        '<span class="article-status {}">{}</span>',
        css_class,
        label,
    )


def _article_row(article, user):
    if article.author:
        author_name = " ".join(
            part
            for part in (
                article.author.first_name,
                article.author.last_name,
            )
            if part
        ) or article.author.username
    else:
        author_name = "Unknown"

    thumbnail = "—"
    if article.thumbnail and article.thumbnail.name:
        thumbnail = format_html(
            '<a href="{}" target="_blank" rel="noopener">Open in new tab</a>',
            article.thumbnail.url,
        )

    return [
        _article_action(article, user),
        _article_status(article),
        conditional_escape(author_name),
        conditional_escape(article.title),
        thumbnail,
        date_format(article.date_created, "d-M-Y"),
    ]


def build_article_management_payload(request):
    draw = _bounded_int(request.GET.get("draw"), 0)
    start = _bounded_int(request.GET.get("start"), 0)
    length = _bounded_int(
        request.GET.get("length"),
        10,
        minimum=1,
        maximum=MAX_ARTICLE_TABLE_PAGE_SIZE,
    )
    search = request.GET.get("search[value]", "").strip()

    base_queryset = _base_article_queryset(request.user)
    records_total = base_queryset.count()
    filtered_queryset = _search_article_queryset(base_queryset, search)
    records_filtered = (
        records_total if not search else filtered_queryset.count()
    )
    articles = _ordered_article_queryset(
        filtered_queryset,
        request.GET,
    )[start : start + length]

    return {
        "draw": draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": [
            _article_row(article, request.user)
            for article in articles
        ],
    }
