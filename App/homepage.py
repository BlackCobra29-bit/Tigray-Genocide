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


HOMEPAGE_SUMMARY_CACHE_KEY = "homepage:summary:v6"
HOMEPAGE_SUMMARY_CACHE_TIMEOUT = 60 * 60

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

PERPETRATOR_GROUPS = [
    ("Died from lack of food", ["Died from lack of food"]),
    ("Killed by Eritrean forces", ["Killed by Eritrean forces"]),
    ("Died from lack of medicine", ["Died from lack of medicine"]),
    ("Killed by Ethiopian forces", ["Killed by Ethiopian forces"]),
    (
        "Killed by Ethiopian and Eritrean forces",
        ["Killed by Ethiopian and Eritrean forces"],
    ),
    (
        "Killed by Amhara militia and Fano",
        [
            "Killed by Amhara militia and Fano",
            "Killed by Amhara militia\xa0and\xa0Fano",
            "Killed by Amhara militiaÂ andÂ Fano",
        ],
    ),
]

GENDER_LABELS = ["Male", "Female", "Unknown"]


def build_homepage_summary():
    count_civilian = Civilian_victims.objects.filter(approval=True).count()
    count_articles = Analysis_articles.objects.filter(approval=True, draft=False).count()
    count_panel = Webinar.objects.count()
    count_photo = Photo_archive.objects.count()
    count_video = Video_archive.objects.count()
    total_unverified = (
        Unverified_civilian.objects.aggregate(total=Sum("number_of_civilian"))["total"] or 0
    )

    zone_counts_verified = {
        item["zone"]: item["count"]
        for item in Civilian_victims.objects.filter(approval=True)
        .values("zone")
        .annotate(count=Count("id"))
    }
    zone_counts_unverified = {
        item["zone"]: item["total"]
        for item in Unverified_civilian.objects.values("zone").annotate(
            total=Sum("number_of_civilian")
        )
    }
    line_data_points = [
        zone_counts_verified.get(zone, 0) + zone_counts_unverified.get(zone, 0)
        for zone in ZONE_LABELS
    ]

    total_count = count_civilian + total_unverified
    if total_count == 0:
        line_percentages = [0] * len(line_data_points)
    else:
        line_percentages = [round((value * 100) / total_count, 2) for value in line_data_points]

    age_aggregates = Civilian_victims.objects.filter(approval=True).aggregate(
        age_0_10=Count("id", filter=Q(age__gt=0, age__lt=11)),
        age_11_17=Count("id", filter=Q(age__gte=11, age__lt=18)),
        age_18_32=Count("id", filter=Q(age__gte=18, age__lt=33)),
        age_33_48=Count("id", filter=Q(age__gte=33, age__lt=49)),
        age_49_63=Count("id", filter=Q(age__gte=49, age__lt=64)),
        age_64_79=Count("id", filter=Q(age__gte=64, age__lt=80)),
        age_80_94=Count("id", filter=Q(age__gte=80, age__lt=95)),
        age_unknown=Count("id", filter=Q(age__isnull=True)),
    )
    bar_data_points = [
        age_aggregates["age_0_10"] or 0,
        age_aggregates["age_11_17"] or 0,
        age_aggregates["age_18_32"] or 0,
        age_aggregates["age_33_48"] or 0,
        age_aggregates["age_49_63"] or 0,
        age_aggregates["age_64_79"] or 0,
        age_aggregates["age_80_94"] or 0,
        age_aggregates["age_unknown"] or 0,
    ]

    if count_civilian == 0:
        bar_percentages = [0] * len(bar_data_points)
    else:
        bar_percentages = [round((value * 100) / count_civilian, 2) for value in bar_data_points]

    perpetrator_counts_verified = {
        item["perpetrator"]: item["count"]
        for item in Civilian_victims.objects.filter(approval=True)
        .values("perpetrator")
        .annotate(count=Count("id"))
    }
    perpetrator_counts_unverified = {
        item["perpetrator"]: item["total"]
        for item in Unverified_civilian.objects.values("perpetrator").annotate(
            total=Sum("number_of_civilian")
        )
    }

    pie_data_points = []
    for display_label, source_labels in PERPETRATOR_GROUPS:
        value = sum(perpetrator_counts_verified.get(label, 0) for label in source_labels)
        value += sum(perpetrator_counts_unverified.get(label, 0) for label in source_labels)
        if value > 0:
            percentage = round((value / total_count) * 100, 1) if total_count else 0
            pie_data_points.append(
                {
                    "y": value,
                    "label": display_label,
                    "legendText": f"{display_label} ({percentage}%)",
                }
            )

    gender_counts_verified = {
        item["gender"]: item["count"]
        for item in Civilian_victims.objects.filter(approval=True)
        .values("gender")
        .annotate(count=Count("id"))
    }
    total_gender_count = sum(gender_counts_verified.get(gender, 0) for gender in GENDER_LABELS)

    doughnut_data_points = []
    for label in GENDER_LABELS:
        value = gender_counts_verified.get(label, 0)
        if value > 0:
            percentage = round((value / total_gender_count) * 100, 1) if total_gender_count else 0
            doughnut_data_points.append(
                {
                    "y": value,
                    "label": label,
                    "legendText": f"{label} ({percentage}%)",
                }
            )

    pie_chart = go.Figure(
        data=[
            go.Pie(
                labels=[item["legendText"] for item in pie_data_points],
                values=[item["y"] for item in pie_data_points],
                hoverinfo="label+value",
                textinfo="value+percent",
                textposition="inside",
            )
        ]
    )
    pie_chart.update_layout(
        autosize=True,
        height=360,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="top", y=1, x=0),
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
        domain=dict(y=[0, 0.6]),
        textfont=dict(color="white", size=14),
    )

    doughnut_chart = go.Figure(
        data=[
            go.Pie(
                labels=[item["legendText"] for item in doughnut_data_points],
                values=[item["y"] for item in doughnut_data_points],
                hole=0.5,
                hoverinfo="label+value",
                textposition="inside",
                textinfo="value+percent",
            )
        ]
    )
    doughnut_chart.update_layout(
        autosize=True,
        height=320,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="top", y=1, x=0),
    )
    doughnut_chart.update_traces(
        marker=dict(colors=["rgb(102, 73, 36)", "rgb(214, 39, 40)", "rgb(36, 102, 71)"]),
        domain=dict(y=[0, 0.72]),
        textfont=dict(color="white", size=14),
    )

    return {
        "counts": {
            "civilian": count_civilian,
            "unverified": total_unverified,
            "articles": count_articles,
            "panel": count_panel,
            "photo": count_photo,
            "video": count_video,
        },
        "lineDataPoints": line_data_points,
        "linePercentages": line_percentages,
        "barDataPoints": bar_data_points,
        "barPercentages": bar_percentages,
        # The template loads the lightweight Plotly basic bundle once. Both
        # charts reuse it instead of embedding copies of the full runtime.
        "pieChartHtml": pie_chart.to_html(full_html=False, include_plotlyjs=False),
        "doughnutChartHtml": plot(
            doughnut_chart,
            output_type="div",
            include_plotlyjs=False,
        ),
    }


def get_homepage_summary(force=False):
    if force:
        summary = build_homepage_summary()
        cache.set(HOMEPAGE_SUMMARY_CACHE_KEY, summary, HOMEPAGE_SUMMARY_CACHE_TIMEOUT)
        return summary

    return cache.get_or_set(
        HOMEPAGE_SUMMARY_CACHE_KEY,
        build_homepage_summary,
        HOMEPAGE_SUMMARY_CACHE_TIMEOUT,
    )


def invalidate_homepage_summary():
    cache.delete(HOMEPAGE_SUMMARY_CACHE_KEY)
