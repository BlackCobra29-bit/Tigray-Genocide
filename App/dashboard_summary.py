from django.core.cache import cache
from django.db.models import Count, Q, Sum
import plotly.graph_objs as go
from plotly.offline import plot

from .models import (
    Analysis_articles,
    Civilian_victims,
    Photo_archive,
    Unverified_civilian,
    Video_archive,
    Webinar,
)


ADMIN_DASHBOARD_SUMMARY_CACHE_KEY = "admin-dashboard:summary:v1"
ADMIN_DASHBOARD_SUMMARY_CACHE_TIMEOUT = 60

ZONE_LABELS = [
    "Western Tigray",
    "Eastern Tigray",
    "Central Tigray",
    "North Western Tigray",
    "Southern Tigray",
    "South Eastern Tigray",
    "Mekelle Special",
    "Other",
]

PERPETRATOR_LABELS = [
    "Died from lack of food",
    "Killed by Eritrean forces",
    "Died from lack of medicine",
    "Killed by Ethiopian forces",
    "Killed by Ethiopian and Eritrean forces",
    "Killed by Amhara militiaÂ andÂ Fano",
]
PERPETRATOR_LABELS[-1] = "Killed by Amhara militia\u00a0and\u00a0Fano"

GENDER_LABELS = ["Male", "Female", "Unknown"]


def _percentages(values, total, precision):
    if not total:
        return [0] * len(values)
    return [round((value * 100) / total, precision) for value in values]


def build_admin_dashboard_summary():
    civilian_aggregates = Civilian_victims.objects.aggregate(
        approved=Count("id", filter=Q(approval=True)),
        pending=Count("id", filter=Q(approval=False)),
        age_0_10=Count(
            "id",
            filter=Q(approval=True, age__gt=0, age__lt=11),
        ),
        age_11_17=Count(
            "id",
            filter=Q(approval=True, age__gte=11, age__lt=18),
        ),
        age_18_32=Count(
            "id",
            filter=Q(approval=True, age__gte=18, age__lt=33),
        ),
        age_33_48=Count(
            "id",
            filter=Q(approval=True, age__gte=33, age__lt=49),
        ),
        age_49_63=Count(
            "id",
            filter=Q(approval=True, age__gte=49, age__lt=64),
        ),
        age_64_79=Count(
            "id",
            filter=Q(approval=True, age__gte=64, age__lt=80),
        ),
        age_80_94=Count(
            "id",
            filter=Q(approval=True, age__gte=80, age__lt=95),
        ),
        age_unknown=Count(
            "id",
            filter=Q(approval=True, age__isnull=True),
        ),
    )
    article_aggregates = Analysis_articles.objects.aggregate(
        approved=Count(
            "id",
            filter=Q(approval=True, draft=False),
        ),
        pending=Count(
            "id",
            filter=Q(approval=False, draft=False),
        ),
    )

    count_civilian = civilian_aggregates["approved"] or 0
    count_pending = (
        (civilian_aggregates["pending"] or 0)
        + (article_aggregates["pending"] or 0)
    )

    verified_zone_counts = {
        item["zone"]: item["count"]
        for item in Civilian_victims.objects.filter(approval=True)
        .values("zone")
        .annotate(count=Count("id"))
    }
    unverified_zone_counts = {
        item["zone"]: item["total"] or 0
        for item in Unverified_civilian.objects.values("zone").annotate(
            total=Sum("number_of_civilian")
        )
    }
    total_unverified = sum(unverified_zone_counts.values())
    line_data_points = [
        verified_zone_counts.get(zone, 0) + unverified_zone_counts.get(zone, 0)
        for zone in ZONE_LABELS
    ]
    line_percentages = _percentages(
        line_data_points,
        count_civilian + total_unverified,
        2,
    )

    bar_data_points = [
        civilian_aggregates["age_0_10"] or 0,
        civilian_aggregates["age_11_17"] or 0,
        civilian_aggregates["age_18_32"] or 0,
        civilian_aggregates["age_33_48"] or 0,
        civilian_aggregates["age_49_63"] or 0,
        civilian_aggregates["age_64_79"] or 0,
        civilian_aggregates["age_80_94"] or 0,
        civilian_aggregates["age_unknown"] or 0,
    ]
    bar_percentages = _percentages(bar_data_points, count_civilian, 2)

    verified_perpetrator_counts = {
        item["perpetrator"]: item["count"]
        for item in Civilian_victims.objects.filter(approval=True)
        .values("perpetrator")
        .annotate(count=Count("id"))
    }
    unverified_perpetrator_counts = {
        item["perpetrator"]: item["total"] or 0
        for item in Unverified_civilian.objects.values("perpetrator").annotate(
            total=Sum("number_of_civilian")
        )
    }

    pie_labels = []
    pie_values = []
    for label in PERPETRATOR_LABELS:
        value = (
            verified_perpetrator_counts.get(label, 0)
            + unverified_perpetrator_counts.get(label, 0)
        )
        if value > 0:
            percentage = round((value / count_civilian) * 100, 1) if count_civilian else 0
            pie_labels.append(f"{label} ({percentage}%)")
            pie_values.append(value)

    pie_chart = go.Figure(
        data=[
            go.Pie(
                labels=pie_labels,
                values=pie_values,
                hoverinfo="label+value",
                textinfo="value+percent",
                textposition="inside",
            )
        ]
    )
    pie_chart.update_layout(
        autosize=True,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="top", y=1.5),
    )
    pie_chart.update_traces(
        marker=dict(
            colors=[
                "rgb(13, 93, 149)",
                "rgb(36, 102, 71)",
                "#2ca02c",
                "#d62728",
                "rgb(126, 34, 189)",
                "rgb(121, 53, 40)",
            ]
        ),
        textinfo="value+percent",
        textfont=dict(color="white", size=14),
    )

    verified_gender_counts = {
        item["gender"]: item["count"]
        for item in Civilian_victims.objects.filter(approval=True)
        .values("gender")
        .annotate(count=Count("id"))
    }
    doughnut_labels = []
    doughnut_values = []
    for label in GENDER_LABELS:
        value = verified_gender_counts.get(label, 0)
        if value > 0:
            percentage = round((value / count_civilian) * 100, 1) if count_civilian else 0
            doughnut_labels.append(f"{label} ({percentage}%)")
            doughnut_values.append(value)

    doughnut_chart = go.Figure(
        data=[
            go.Pie(
                labels=doughnut_labels,
                values=doughnut_values,
                hole=0.5,
                hoverinfo="label+value",
                textposition="inside",
                textinfo="value+percent",
            )
        ]
    )
    doughnut_chart.update_traces(
        marker=dict(
            colors=[
                "rgb(102, 73, 36)",
                "rgb(214, 39, 40)",
                "rgb(36, 102, 71)",
            ]
        ),
        textinfo="value+percent",
        textfont=dict(color="white", size=14),
    )

    return {
        "pending_count": count_pending,
        "count_pending": count_pending,
        "count_civilian": count_civilian,
        "count_articles": article_aggregates["approved"] or 0,
        "count_panel": Webinar.objects.count(),
        "count_photo": Photo_archive.objects.count(),
        "count_video": Video_archive.objects.count(),
        "line_data_points": line_data_points,
        "bar_data_points": bar_data_points,
        "line_chart_items_percentage": line_percentages,
        "bar_chart_items_percentage": bar_percentages,
        "pi_data_points": pie_chart.to_html(
            full_html=False,
            include_plotlyjs=False,
        ),
        "doughnut_data_points": plot(
            doughnut_chart,
            output_type="div",
            include_plotlyjs=False,
        ),
    }


def get_admin_dashboard_summary(force=False):
    if force:
        summary = build_admin_dashboard_summary()
        cache.set(
            ADMIN_DASHBOARD_SUMMARY_CACHE_KEY,
            summary,
            ADMIN_DASHBOARD_SUMMARY_CACHE_TIMEOUT,
        )
        return summary

    return cache.get_or_set(
        ADMIN_DASHBOARD_SUMMARY_CACHE_KEY,
        build_admin_dashboard_summary,
        ADMIN_DASHBOARD_SUMMARY_CACHE_TIMEOUT,
    )


def invalidate_admin_dashboard_summary():
    cache.delete(ADMIN_DASHBOARD_SUMMARY_CACHE_KEY)
