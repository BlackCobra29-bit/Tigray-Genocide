# import libraries to export SQL backup
import subprocess
import os
from django.conf import settings
from django.http import Http404, HttpResponse
from datetime import datetime
from django.db.models import Sum, Count
# end of block
from django.shortcuts import render, redirect
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from .models import Civilian_victims
from .models import Analysis_articles
from .models import Article_comments
from .models import Webinar
from .models import Photo_archive
from .models import Video_archive
from .models import Administrator
from .models import Tigray_woreda
from .models import Hero_images
from .models import Webmail_password_manager
from .models import Unverified_civilian
from django.contrib import messages
from django.views.generic import DeleteView, UpdateView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from .forms import Civilian_Victim_Form
from .forms import AnalysisArticleForm
from .forms import Webinar_discussion_Form
from .forms import Photo_Archive_Form
from .forms import Video_Archive_Form
from .forms import Approve_Civilian_Victim_Form
from .forms import Approve_Analysis_Form
from .forms import Administrator_form
from .forms import Unverified_civilian_form
from .forms import LoginCaptchaForm
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import serializers
from django.db.models import Q
from django.http import JsonResponse
from colorama import Fore
from django.core.mail import EmailMessage
from django.conf import settings
import folium
import random
import string
import plotly.graph_objs as go
from plotly.offline import plot
import urllib.parse
from django.utils.text import slugify
# to purse video url id
from urllib.parse import urlparse, parse_qs
from .admin_civilian_form import get_admin_civilian_woreda_names
from .admin_metrics import get_admin_pending_count
from .civilian_exports import (
    SUPPORTED_EXPORT_FORMATS,
    build_civilian_export_payload,
    build_civilian_export_response,
)
from .civilian_management import (
    build_civilian_management_payload,
    build_unverified_export_payload,
    build_unverified_management_payload,
)
from .dashboard_summary import get_admin_dashboard_summary
from .homepage import get_homepage_summary
from .image_optimization import get_optimized_image_url
from .victim_map_cache import (
    VICTIM_MAP_HTML_CACHE_TIMEOUT,
    get_victim_map_cache_version,
)

def custom_404_view(request, exception):
    
    return render(request, '404.html', status=404)


def get_random_instance(queryset):
    total = queryset.count()
    if total == 0:
        return None
    random_index = random.randrange(total)
    return queryset.all()[random_index]


def get_random_queryset(queryset, exclude_id=None, sample_size=10):
    if exclude_id is not None:
        queryset = queryset.exclude(id=exclude_id)
    total = queryset.count()
    if total <= sample_size:
        return list(queryset)
    random_indexes = random.sample(range(total), sample_size)
    return [queryset.all()[index] for index in random_indexes]


PUBLIC_TABLE_PAGE_SIZE = 10
PUBLIC_GRID_BATCH_SIZE = 30
PUBLIC_ARCHIVE_PAGE_SIZE = 30
PUBLIC_ARTICLE_PAGE_SIZE = 12


def is_htmx_request(request):
    return request.headers.get('HX-Request') == 'true'


def is_partial_request(request):
    return (
        is_htmx_request(request)
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    ) and request.headers.get('HX-Boosted') != 'true'


def render_public_response(request, template_name, context, partial_template=None):
    if partial_template and is_partial_request(request):
        return render(request, partial_template, context)
    return render(request, template_name, context)


def get_public_woredas():
    return cache.get_or_set(
        'public_woreda_list',
        lambda: list(
            Tigray_woreda.objects.only(
                'woreda_name',
                'latitude',
                'longitude',
                'zone',
            )
        ),
        300,
    )


def paginate_request_queryset(request, queryset, per_page):
    return Paginator(queryset, per_page).get_page(request.GET.get('page') or 1)


def build_querystring(request, **updates):
    params = request.GET.copy()
    for key, value in updates.items():
        if value in (None, ''):
            params.pop(key, None)
        else:
            params[key] = str(value)
    return params.urlencode()


def get_verified_victim_queryset():
    return Civilian_victims.objects.filter(approval=True).select_related('woreda').only(
        'id',
        'full_name',
        'gender',
        'age',
        'perpetrator',
        'place_of_killing',
        'woreda__woreda_name',
        'source',
        'source_link',
        'date_of_event',
        'remark',
        'picture',
        'date_created',
    )


def filter_verified_victims(queryset, request):
    query = request.GET.get('q', '').strip()
    perpetrator = request.GET.get('perpetrator', '').strip()
    woreda = request.GET.get('woreda', '').strip()
    gender = request.GET.get('gender', '').strip()
    sort = request.GET.get('sort', 'newest').strip()

    if query:
        queryset = queryset.filter(
            Q(full_name__icontains=query)
            | Q(place_of_killing__icontains=query)
            | Q(source__icontains=query)
            | Q(remark__icontains=query)
        )
    if perpetrator:
        queryset = queryset.filter(perpetrator=perpetrator)
    if woreda:
        queryset = queryset.filter(woreda_id=woreda)
    if gender:
        queryset = queryset.filter(gender=gender)

    sort_map = {
        'newest': '-date_created',
        'oldest': 'date_created',
        'name': 'full_name',
        'event_date': '-date_of_event',
    }
    return queryset.order_by(sort_map.get(sort, '-date_created'))


def get_unverified_victim_queryset():
    return Unverified_civilian.objects.select_related('woreda').only(
        'id',
        'location',
        'number_of_civilian',
        'perpetrator',
        'woreda__woreda_name',
        'source',
        'source_link',
        'remark',
        'date_created',
    )


def filter_unverified_victims(queryset, request):
    query = request.GET.get('q', '').strip()
    perpetrator = request.GET.get('perpetrator', '').strip()
    woreda = request.GET.get('woreda', '').strip()

    if query:
        queryset = queryset.filter(
            Q(location__icontains=query)
            | Q(source__icontains=query)
            | Q(remark__icontains=query)
        )
    if perpetrator:
        queryset = queryset.filter(perpetrator=perpetrator)
    if woreda:
        queryset = queryset.filter(woreda_id=woreda)
    return queryset


def get_victim_photo_queryset():
    return get_verified_victim_queryset().only(
        'id',
        'full_name',
        'picture',
        'perpetrator',
        'woreda__woreda_name',
        'date_created',
    )


def get_photo_archive_queryset():
    return Photo_archive.objects.select_related('woreda').only(
        'id',
        'location',
        'woreda__woreda_name',
        'date_of_event',
        'description',
        'photo',
        'graphic',
        'date_created',
    )


def build_victim_map(selected_woreda=None):
    woreda_list = get_public_woredas()
    map_cache_key = (
        f'public_victim_map_html:v1:{get_victim_map_cache_version()}:'
        f'{slugify(selected_woreda) if selected_woreda else "all"}'
    )
    cached_map = cache.get(map_cache_key)
    if cached_map is not None:
        return cached_map, woreda_list

    victim_counts = {
        item['woreda']: item['total']
        for item in Civilian_victims.objects.filter(approval=True, woreda__isnull=False)
        .values('woreda')
        .annotate(total=Count('id'))
    }
    map_center = [13.881273, 39.127495]

    if selected_woreda:
        selected_obj = next((item for item in woreda_list if item.woreda_name == selected_woreda), None)
        if selected_obj:
            map_center = [selected_obj.latitude, selected_obj.longitude]

    folium_map = folium.Map(
        location=map_center,
        zoom_start=10 if selected_woreda else 7,
        width='100%',
        height='100%',
        tiles=None,
    )
    folium.TileLayer(
        'openstreetmap',
        attr='OpenStreetMap',
        name='OpenStreetMap',
    ).add_to(folium_map)
    folium.LayerControl().add_to(folium_map)

    for woreda in woreda_list:
        if woreda.woreda_name == 'Other':
            continue
        victim_total = victim_counts.get(woreda.woreda_name, 0)
        if not victim_total:
            continue

        popup_content = (
            f'<b><a title="Get full information" href="/Civilina-victims-location-information/{slugify(woreda.woreda_name)}" '
            f'target="_top">{woreda.woreda_name} Woreda</a></b><br>Civilian Victims: {victim_total}'
        )
        popup = folium.Popup(folium.Html(popup_content, script=True), max_width=300)
        marker_kwargs = {'popup': popup}
        if selected_woreda and woreda.woreda_name == selected_woreda:
            marker_kwargs['icon'] = folium.Icon(color='red', icon='star')
        folium.Marker((woreda.latitude, woreda.longitude), **marker_kwargs).add_to(folium_map)

    rendered_map = folium_map._repr_html_()
    cache.set(map_cache_key, rendered_map, VICTIM_MAP_HTML_CACHE_TIMEOUT)
    return rendered_map, woreda_list


@cache_page(60)
def index(request):
    random_hero_image = get_random_instance(Hero_images.objects.only('hero_image'))
    hero_image_url = (
        get_optimized_image_url(
            random_hero_image.hero_image,
            max_width=1920,
            max_height=1080,
            quality=84,
        )
        if random_hero_image
        else ''
    )

    home_page_config = get_homepage_summary()

    civilian_victims = Civilian_victims.objects.filter(approval=True).only(
        'id',
        'full_name',
        'picture',
    ).exclude(
        Q(picture='civilian_victims_pic/default.png') | Q(picture='civilian_victims_pic/default_female.jpg')
    )[:30]
    analysis_articles = Analysis_articles.objects.filter(approval=True, draft=False).select_related(
        'author', 'author__administrator'
    ).only(
        'id', 'title', 'thumbnail', 'date_created', 'author__first_name', 'author__last_name',
        'author__administrator__admin_photo'
    )[:9]
    photo_archives = Photo_archive.objects.select_related('woreda').only(
        'id', 'location', 'woreda__woreda_name', 'date_of_event', 'description', 'photo', 'graphic'
    )[:12]
    video_archives = Video_archive.objects.select_related('woreda').only(
        'id', 'description', 'location', 'woreda__woreda_name', 'online_link', 'date_of_event'
    )[:12]

    context = {
        'hero_image': hero_image_url,
        'civilian_victims': civilian_victims,
        'analysis_articles': analysis_articles,
        'photo_archives': photo_archives,
        'video_archives': video_archives,
        'home_page_config': home_page_config,
        'home_page_client_config': {
            key: value
            for key, value in home_page_config.items()
            if not key.endswith('Html')
        },
        'pie_chart_html': home_page_config.get('pieChartHtml', ''),
        'doughnut_chart_html': home_page_config.get('doughnutChartHtml', ''),
    }

    return render(request, 'index.html', context)

    """

    # line chart
    zone_list = ['Western Tigray', 'Eastern Tigray', 'Central Tigray', 'North Western Tigray',
                 'Southern Tigray', 'South Eastern Tigray', 'Mekelle Special', 'Other']

    zone_counts_verified = {
        item['zone']: item['count']
        for item in Civilian_victims.objects.filter(approval=True).values('zone').annotate(count=Count('id'))
    }
    zone_counts_unverified = {
        item['zone']: item['total']
        for item in Unverified_civilian.objects.values('zone').annotate(total=Sum('number_of_civilian'))
    }

    line_chart_data_points = [
        zone_counts_verified.get(zone, 0) + zone_counts_unverified.get(zone, 0)
        for zone in zone_list
    ]

    total_unverified = Unverified_civilian.objects.aggregate(total=Sum('number_of_civilian'))['total'] or 0
    total_count = count_civilian + total_unverified
    if total_count == 0:
        line_chart_items_percentage = [0] * len(line_chart_data_points)
    else:
        line_chart_items_percentage = [round((value * 100) / total_count, 2) for value in line_chart_data_points]


    # bar chart
    age_aggregates = Civilian_victims.objects.filter(approval=True).aggregate(
        age_0_10=Count('id', filter=Q(age__gt=0, age__lt=11)),
        age_11_17=Count('id', filter=Q(age__gte=11, age__lt=18)),
        age_18_32=Count('id', filter=Q(age__gte=18, age__lt=33)),
        age_33_48=Count('id', filter=Q(age__gte=33, age__lt=49)),
        age_49_63=Count('id', filter=Q(age__gte=49, age__lt=64)),
        age_64_79=Count('id', filter=Q(age__gte=64, age__lt=80)),
        age_80_94=Count('id', filter=Q(age__gte=80, age__lt=95)),
        age_unknown=Count('id', filter=Q(age__isnull=True))
    )

    bar_chart_data_points = [
        age_aggregates['age_0_10'] or 0,
        age_aggregates['age_11_17'] or 0,
        age_aggregates['age_18_32'] or 0,
        age_aggregates['age_33_48'] or 0,
        age_aggregates['age_49_63'] or 0,
        age_aggregates['age_64_79'] or 0,
        age_aggregates['age_80_94'] or 0,
        age_aggregates['age_unknown'] or 0
    ]

    if count_civilian == 0:
        bar_chart_items_percentage = [0] * len(bar_chart_data_points)
    else:
        bar_chart_items_percentage = [round((value * 100) / count_civilian, 2) for value in bar_chart_data_points]


    # Pie Chart

    perpetrator_list = [
        'Died from lack of food',
        'Killed by Eritrean forces',
        'Died from lack of medicine',
        'Killed by Ethiopian forces',
        'Killed by Ethiopian and Eritrean forces',
        'Killed by Amhara militia and Fano'
    ]

    perpetrator_counts_verified = {
        item['perpetrator']: item['count']
        for item in Civilian_victims.objects.filter(approval=True).values('perpetrator').annotate(count=Count('id'))
    }
    perpetrator_counts_unverified = {
        item['perpetrator']: item['total']
        for item in Unverified_civilian.objects.values('perpetrator').annotate(total=Sum('number_of_civilian'))
    }

    pi_chart_data_points = []
    verified_legend = []
    for item in perpetrator_list:
        total_items = perpetrator_counts_verified.get(item, 0) + perpetrator_counts_unverified.get(item, 0)
        if total_items > 0 and total_count > 0:
            pi_chart_data_points.append(total_items)
            verified_legend.append(f"{item} ({round((total_items / total_count) * 100, 1)}%)")

    pie_chart = go.Figure(data=[go.Pie(labels=verified_legend, values=pi_chart_data_points,
                hoverinfo='label+value', textinfo='value+percent', textposition='inside')])

    pie_chart.update_layout(
        autosize=True,
        height=360,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation='h', yanchor='top', y=1, x=0)
    )

    pie_chart.update_traces(
        marker=dict(colors=['rgb(13, 93, 149)', 'rgb(36, 102, 71)', '#2ca02c', '#d62728', 'rgb(126, 34, 189)', 'rgb(121, 53, 40)']),
        domain=dict(y=[0, 0.6]),
        textinfo='value+percent',
        textfont=dict(color='white', size=14)
    )
    # Doughnut Chart

    gender_list = ['Male', 'Female', 'Unknown']
    gender_counts_verified = {
        item['gender']: item['count']
        for item in Civilian_victims.objects.filter(approval=True).values('gender').annotate(count=Count('id'))
    }

    total_gender_count = sum(gender_counts_verified.get(gender, 0) for gender in gender_list)

    verified_legend = []
    doughnut_chart_data_points = []
    for gender in gender_list:
        count_items = gender_counts_verified.get(gender, 0)
        if count_items > 0 and total_gender_count > 0:
            doughnut_chart_data_points.append(count_items)
            verified_legend.append(f"{gender} ({round((count_items / total_gender_count) * 100, 1)}%)")

    # Create the donut chart

    donut_chart = go.Figure(data=[go.Pie(labels=verified_legend, values=doughnut_chart_data_points, hole=0.5, 

            hoverinfo='label+value', textposition='inside', textinfo='value+percent')])

    # Update the layout to increase width and height
    donut_chart.update_layout(
    autosize=True,  # Enable autosizing to make the chart responsive
    height=320,
    margin=dict(l=0, r=0, t=0, b=0),  # Adjust margin as needed
    legend=dict(orientation="h", yanchor="top", y=1, x=0),  # Position legend at the top
)

    donut_chart.update_traces(marker=dict(colors=['rgb(102, 73, 36)', 'rgb(214, 39, 40)', 'rgb(36, 102, 71)']),

        domain=dict(y=[0, 0.72]), textinfo='value+percent', textfont=dict(color='white', size=14))



    # Convert the chart to HTML

    doughnut_plot_div = plot(donut_chart, output_type='div')

    # get sum of unverified ciivilians
    total_civilians = Unverified_civilian.objects.aggregate(total_civilians=Sum('number_of_civilian'))['total_civilians'] or 0
    
    context = {
        # counter data
        'count_civilian': count_civilian,
        'count_articles': count_articles,
        'count_panel': count_panel,
        'count_photo': count_photo,
        'count_video': count_video,
        'count_unverified_civilian':total_civilians,
        # hero image object
        'hero_image': random_hero_image.hero_image.url if random_hero_image else '',
        # section data
        'civilian_victims': civilian_victims,
        'analysis_articles': analysis_articles,
        # Chart data
        'line_data_points': line_chart_data_points,
        'bar_data_points': bar_chart_data_points,
        'bar_chart_items_percentage': bar_chart_items_percentage,
        'line_chart_items_percentage': line_chart_items_percentage,
        'photo_archives': photo_archives,
        'video_archives': video_archives,
        'pi_data_points': pie_chart.to_html(full_html=False),
        'doughnut_data_points': doughnut_plot_div,
        'home_page_config': {
            'counts': {
                'civilian': count_civilian,
                'unverified': total_civilians,
                'articles': count_articles,
                'photo': count_photo,
                'video': count_video,
            },
            'lineDataPoints': line_chart_data_points,
            'linePercentages': line_chart_items_percentage,
            'barDataPoints': bar_chart_data_points,
            'barPercentages': bar_chart_items_percentage,
        },
    }

    return render(request, 'index.html', context)
    """


def civilian_victims_by_name(request):
    filtered_queryset = filter_verified_victims(get_verified_victim_queryset(), request)
    page_obj = paginate_request_queryset(request, filtered_queryset, PUBLIC_TABLE_PAGE_SIZE)
    filtered_count = page_obj.paginator.count
    context = {
        'page_obj': page_obj,
        'page': page_obj,
        'civilian_victims': page_obj.object_list,
        'total_count': filtered_count,
        'filtered_count': filtered_count,
        'woreda_list': get_public_woredas(),
        'filters': {
            'q': request.GET.get('q', '').strip(),
            'perpetrator': request.GET.get('perpetrator', '').strip(),
            'woreda': request.GET.get('woreda', '').strip(),
            'gender': request.GET.get('gender', '').strip(),
            'sort': request.GET.get('sort', 'newest').strip(),
        },
        'querystring_builder': request.GET.urlencode(),
    }
    return render_public_response(
        request,
        'civilian_victims_by_name.html',
        context,
        partial_template='public_partials/civilian_victim_results.html',
    )

def Civilian_victim_photo_page(request):
    filtered_queryset = filter_verified_victims(get_victim_photo_queryset(), request)
    page_obj = paginate_request_queryset(request, filtered_queryset, PUBLIC_GRID_BATCH_SIZE)
    filtered_count = page_obj.paginator.count
    context = {
        'page_obj': page_obj,
        'page': page_obj,
        'civilian_queryset': page_obj.object_list,
        'filtered_count': filtered_count,
        'woreda_list': get_public_woredas(),
        'filters': {
            'q': request.GET.get('q', '').strip(),
            'perpetrator': request.GET.get('perpetrator', '').strip(),
            'woreda': request.GET.get('woreda', '').strip(),
        },
        'next_querystring': build_querystring(request, page=page_obj.next_page_number()) if page_obj.has_next() else '',
    }
    if is_partial_request(request) and (request.GET.get('append') == '1' or request.GET.get('page')):
        return render(request, 'public_partials/victim_photo_batch.html', context)
    return render_public_response(
        request,
        'civilin_vicitm_photo_page.html',
        context,
        partial_template='public_partials/victim_photo_grid.html',
    )
    
# a method view to search a specfic civilian victim
def Search_civilian(request):
    query_params = {}
    if request.GET.get('atrocity'):
        query_params['perpetrator'] = request.GET.get('atrocity')
    if request.GET.get('woreda'):
        query_params['woreda'] = request.GET.get('woreda')
    if request.GET.get('q'):
        query_params['q'] = request.GET.get('q')
    querystring = urllib.parse.urlencode(query_params)
    return redirect(f"{reverse('civilian-victim-photo-page')}?{querystring}" if querystring else reverse('civilian-victim-photo-page'))


def Civilian_victim_by_map(request):
    geolocation, woreda_list = build_victim_map()
    context = {
        'geolocation': geolocation,
        'woreda_list': woreda_list,
    }

    return render(request, 'civilian_victims_map.html', context)

def Civilian_victim_by_map_info(request, woreda_pr):
    woreda_pr = woreda_pr.title().replace('-', ' ')
    geolocation, woreda_list = build_victim_map(selected_woreda=woreda_pr)
    civilian_victims_by_woreda = get_verified_victim_queryset().filter(woreda_id=woreda_pr)
    page_obj = paginate_request_queryset(request, civilian_victims_by_woreda, 10)

    context = {
        'geolocation': geolocation,
        'civilian_victims': page_obj.object_list,
        'page_obj': page_obj,
        'page': page_obj,
        'woreda_list': woreda_list,
        'selected_woreda': woreda_pr,
    }
    
    return render(request, 'civilian_victims_map_info.html', context)

def view_victim_info(request, id):
    civilian_victim_item = get_object_or_404(
        Civilian_victims.objects.filter(approval=True).select_related('woreda').only(
            'id',
            'full_name',
            'gender',
            'age',
            'perpetrator',
            'place_of_killing',
            'woreda__woreda_name',
            'source',
            'source_link',
            'date_of_event',
            'remark',
            'picture',
        ),
        id=id,
    )

    context = {
        'item': civilian_victim_item
    }

    return render(request, 'view_victim_info.html', context)

def unverified_civilian_victims_by_name(request):
    filtered_queryset = filter_unverified_victims(get_unverified_victim_queryset(), request)
    page_obj = paginate_request_queryset(request, filtered_queryset, PUBLIC_TABLE_PAGE_SIZE)
    context = {
        'page_obj': page_obj,
        'page': page_obj,
        'civilian_victims': page_obj.object_list,
        'filtered_count': filtered_queryset.count(),
        'total_civilians': filtered_queryset.aggregate(total_civilians=Sum('number_of_civilian'))['total_civilians'] or 0,
        'woreda_list': get_public_woredas(),
        'filters': {
            'q': request.GET.get('q', '').strip(),
            'perpetrator': request.GET.get('perpetrator', '').strip(),
            'woreda': request.GET.get('woreda', '').strip(),
        },
    }

    return render_public_response(
        request,
        'unverified_civilian_victim.html',
        context,
        partial_template='public_partials/unverified_results.html',
    )


def View_article(request, id):
    article_queryset = Analysis_articles.objects.filter(approval=True, draft=False).select_related(
        'author', 'author__administrator'
    ).only(
        'id',
        'title',
        'thumbnail',
        'content',
        'endf_related',
        'personal_account',
        'date_created',
        'author__first_name',
        'author__last_name',
        'author__administrator__admin_photo',
    )
    random_analysis_articles = get_random_queryset(
        article_queryset.only('id', 'title', 'thumbnail', 'date_created'),
        exclude_id=id,
        sample_size=10,
    )
    article_counts = Analysis_articles.objects.filter(approval=True, draft=False).aggregate(
        general_articles=Count('id', filter=Q(endf_related=False, personal_account=False)),
        endf_articles=Count('id', filter=Q(endf_related=True)),
        personal_acc=Count('id', filter=Q(personal_account=True)),
    )
    analysis_article_item = get_object_or_404(article_queryset, id=id)
    analysis_article_comments = Article_comments.objects.filter(article=analysis_article_item).only(
        'name', 'content', 'date_created'
    )

    context = {
        'random_articles': random_analysis_articles,
        'general_articles': article_counts['general_articles'],
        'endf_articles': article_counts['endf_articles'],
        'personal_acc': article_counts['personal_acc'],
        'item': analysis_article_item,
        'comments': analysis_article_comments
    }

    return render(request, 'view_article.html', context)


def Article_comment(request, article_id):

    if request.method == 'POST':

        article_object = Analysis_articles.objects.get(
            id=article_id, approval=True, draft=False)
        Article_comments.objects.create(article=article_object, name=request.POST.get('name'), email=request.POST.get('email'),
                                        content=request.POST.get('comment'))

        print('Comment added successfully')

        return redirect(f'/View-article/{article_id}')

    return None


def Articles_page(request):
    total_articles = Analysis_articles.objects.filter(approval=True, draft=False).select_related(
        'author', 'author__administrator'
    ).only(
        'id', 'title', 'thumbnail', 'date_created', 'author__first_name', 'author__last_name',
        'author__administrator__admin_photo'
    )
    page = paginate_request_queryset(request, total_articles, PUBLIC_ARTICLE_PAGE_SIZE)

    context = {
        'page': page
    }

    return render(request, 'analysis_articles_page.html', context)

def General_category_articles(request, category):
    article_queryset = Analysis_articles.objects.filter(approval=True, draft=False).select_related(
        'author', 'author__administrator'
    ).only(
        'id', 'title', 'thumbnail', 'date_created', 'author__first_name', 'author__last_name',
        'author__administrator__admin_photo'
    )
    if category == 'general':
        article_queryset = article_queryset.filter(endf_related=False, personal_account=False)
    elif category == 'personal':
        article_queryset = article_queryset.filter(personal_account=True)
    elif category == 'endf':
        article_queryset = article_queryset.filter(endf_related=True)
    page = paginate_request_queryset(request, article_queryset, PUBLIC_ARTICLE_PAGE_SIZE)

    context = {
        'page': page
    }

    return render(request, 'articles_category.html', context)

def Search_article(request):
    search_query = (request.GET.get('q') or request.POST.get('search_query') or '').strip()
    searched_articles = Analysis_articles.objects.filter(
        approval=True,
        draft=False,
        title__icontains=search_query,
    ).select_related('author', 'author__administrator').only(
        'id', 'title', 'thumbnail', 'date_created', 'author__first_name', 'author__last_name',
        'author__administrator__admin_photo'
    ) if search_query else Analysis_articles.objects.none()

    context = {
        'search_result': searched_articles,
        'search_query': search_query,
    }

    return render(request, 'search_articles.html', context)

def Webinar_discussion_page(request):
    toatl_discussion = Webinar.objects.select_related('author').only(
        'id', 'webinar_title', 'webinar_video_url', 'date_created', 'author__first_name', 'author__last_name'
    )
    page = paginate_request_queryset(request, toatl_discussion, PUBLIC_ARTICLE_PAGE_SIZE)

    context = {
        'page': page
    }

    return render(request, 'webinar_discussion.html', context)


def View_webinar_discussion(request, id):
    webinar_discussion_item = get_object_or_404(
        Webinar.objects.select_related('author').only(
            'id', 'webinar_title', 'webinar_content', 'webinar_video_url', 'date_created',
            'author__first_name', 'author__last_name'
        ),
        id=id,
    )

    context = {
        'item': webinar_discussion_item,
    }

    return render(request, 'view_panel_discussion.html', context)

def Archive_photo(request):
    woreda = request.GET.get('woreda', '').strip()
    photo_archives = get_photo_archive_queryset()
    if woreda:
        photo_archives = photo_archives.filter(woreda_id=woreda)
    page = paginate_request_queryset(request, photo_archives, PUBLIC_ARCHIVE_PAGE_SIZE)

    context = {
        'page': page,
        'filtered_count': photo_archives.count(),
        'woreda_list': get_public_woredas(),
        'woreda': woreda,
        'next_querystring': build_querystring(request, page=page.next_page_number()) if page.has_next() else '',
    }
    if is_partial_request(request) and (request.GET.get('append') == '1' or request.GET.get('page')):
        return render(request, 'public_partials/photo_archive_batch.html', context)

    return render_public_response(
        request,
        'archive_by_photo.html',
        context,
        partial_template='public_partials/photo_archive_results.html',
    )
    
# a method view to search a specfic photo archive by woreda
def Search_archive_photo(request):
    querystring = urllib.parse.urlencode({'woreda': request.GET.get('woreda', '').strip()})
    return redirect(f"{reverse('archive-photo')}?{querystring}" if querystring else reverse('archive-photo'))


def Archive_video(request):
    video_archives = Video_archive.objects.select_related('woreda').only(
        'id', 'location', 'woreda__woreda_name', 'date_of_event', 'description', 'online_link', 'date_created'
    )
    page = paginate_request_queryset(request, video_archives, PUBLIC_ARCHIVE_PAGE_SIZE)

    context = {
        'page': page
    }

    return render(request, 'archive_by_video.html', context)

def Watch_video(request, id):
    video_queryset = Video_archive.objects.select_related('woreda').only(
        'id', 'location', 'woreda__woreda_name', 'date_of_event', 'description', 'online_link', 'date_created'
    )
    get_obj = get_object_or_404(video_queryset, id=id)
    random_video_archives = get_random_queryset(video_queryset, exclude_id=id, sample_size=10)

    context = {
        'current_video': get_obj,
        'random_video': random_video_archives
    }

    return render(request, 'watch_video.html', context)


def Send_us_information(request):

    context = {
        'woreda_list': Tigray_woreda.objects.all(),
    }

    if request.method == 'POST':
        civilian_model = Civilian_victims()
        civilian_model.sender_fullname = request.POST.get('sender_fullname')
        civilian_model.sender_location = request.POST.get('sender_address')
        civilian_model.sender_email = request.POST.get('sender_email')
        civilian_model.sender_phone = request.POST.get('sender_phone')
        civilian_model.full_name = request.POST.get(
            'first_name') + ' ' + request.POST.get('middle_name') + ' ' + request.POST.get('last_name')
        civilian_model.gender = request.POST.get('gender')
        civilian_model.age = request.POST.get('age') or None
        if request.FILES.get('photo'):
            civilian_model.picture = request.FILES.get('photo')
        else:
            if request.POST.get('gender') == 'Male':
                civilian_model.picture = "civilian_victims_pic/default.png"
            else:
                civilian_model.picture = "civilian_victims_pic/default_female.jpg"
        civilian_model.perpetrator = request.POST.get('perpetrator')
        woreda_obj = Tigray_woreda.objects.get(woreda_name = request.POST.get('woreda'))
        civilian_model.woreda = woreda_obj
        civilian_model.zone = woreda_obj.zone
        civilian_model.place_of_killing = request.POST.get('place')
        civilian_model.date_of_event = request.POST.get('date_of_event') or None
        civilian_model.remark = request.POST.get('remark')

        civilian_model.save()

        return JsonResponse({'success': True})

    return render(request, 'send_us_information.html', context)
    
def Send_archive(request):
    
    context = {
        'woreda_list': Tigray_woreda.objects.all(),
    }
    
    if request.method == 'POST':
        # email message setting
        archive_file = request.FILES['photo']
        email_subject = request.POST['sender_email']
        email_body = '''
                <!DOCTYPE html
                PUBLIC "-//W3C//DTD XHTML 1.0 Transitional //EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office"
                xmlns:v="urn:schemas-microsoft-com:vml" lang="en">
            
            <head>
                <link rel="stylesheet" type="text/css" hs-webfonts="true"
                    href="https://fonts.googleapis.com/css?family=Lato|Lato:i,b,bi">
                <title>Email template</title>
                <meta property="og:title" content="Email template">
            
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            
                <meta http-equiv="X-UA-Compatible" content="IE=edge">
            
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            
            
            </head>
            
            <body bgcolor="#F5F8FA"
                style="width: 100%; margin: auto 0; padding:0; font-family:Lato, sans-serif; font-size:18px; color:#33475B; word-break:break-word">
            
                <! View in Browser Link -->
            
                    <div id="email" style="margin: auto;
                    width: 600px;
                    background-color: white;">
                        <table align="right" role="presentation">
                            <tr>
                                <td style="vertical-align: top;">
                                    <a class="subtle-link" style="text-decoration: underline;
                    color: inherit;
                    font-weight: bold;
                    color: #253342; font-size: 9px; 
                    text-transform:uppercase; 
                    letter-spacing: 1px;
                    color: #CBD6E2;" href="#">View in Browser</a>
                                </td>
                            <tr>
                        </table>
            
            
                        <! Banner -->
                            <table role="presentation" width="100%">
                                <tr>
            
                                    <td bgcolor="black" align="center" style="color: white;vertical-align: top;">
            
                                        <h3><i>tigraygenocide.com</i> Archive Information </h3>
            
                                    </td>
                            </table>
            
                            <br><br>
            
                            <! First Row -->
            
                                <table role="presentation" border="0" cellpadding="0" cellspacing="10px"
                                    style="padding: 30px 30px 30px 60px;">
                                    <tr>
                                        <td style="vertical-align: top;">
                                            <ul>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Sender Fullname: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Sender Email: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Sender Address: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Sender Phone: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Location: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Woreda: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Date of event:: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
                                                <li>
                                                    <p style="text-weight: normal; font-weight: 100;">Description:: <b
                                                            style="color: #73879C">{}</b></p>
                                                </li>
            
                                            </ul>
                                        </td>
                                    </tr>
                                </table>
            
                    </div>
            </body>
            
            </html>
            '''.format(request.POST.get('sender_fullname'), request.POST.get('sender_email'), request.POST.get('sender_address'), request.POST['sender_phone'], request.POST['location'], request.POST['woreda'], request.POST['date_of_event'], request.POST['description'])
    
        email_from = request.POST['sender_email']
        email_to = [settings.EMAIL_HOST_USER]

        msg = EmailMessage(email_subject, email_body, email_from, email_to)
        msg.attach(archive_file.name, archive_file.read(), archive_file.content_type)
        msg.content_subtype = "html"  # Set the content type to HTML
        # Send the email
        msg.send()
        
        return JsonResponse({'success': True})
    
    return render(request, 'send-archive.html', context)

def About_us(request):

    return render(request, 'about_us.html')

def Contact_us(request):
    
    if request.method == 'POST':
        email_subject = request.POST['sender_subject']
        email_body = request.POST['sender_message']
        email_from = request.POST['sender_email']
        email_to = [settings.EMAIL_HOST_USER]

        msg = EmailMessage(email_subject, email_body, email_from, email_to)
        msg.content_subtype = "html"  # Set the content type to HTML

        # Send the email
        msg.send()
        
        return JsonResponse({'success': True})

    return render(request, 'contact-us.html')


""" 
Adminstrator Page View Methods
"""


def Admin_login(request):

    form = LoginCaptchaForm()

    if request.user.is_authenticated:

        return redirect('/Admin-dashboard')

    else:

        if request.method == 'POST':

            username = request.POST.get('login_username')
            password = request.POST.get('login_password')
            # authenticate user
            user_auth = authenticate(username=username, password=password)
            if user_auth is not None:
                form = LoginCaptchaForm(request.POST)
                if form.is_valid():
                    human = True
                    login(request, user_auth)
                    return redirect('/Admin-dashboard')
            else:
                messages.error(request, 'Incorrect login credenials')
                return redirect('/Adminstrator-login-page')

    return render(request, 'admin_templates/account_templates/login.html', {'captcha_form': form})

def Admin_logout(request):

    logout(request)

    return redirect('/Adminstrator-login-page')


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def admin_dashboard(request):
    administrator = Administrator.objects.get(user=request.user)
    request.user._state.fields_cache["administrator"] = administrator
    context = {
        **get_admin_dashboard_summary(),
        "Administrator": administrator,
    }
    return render(request, 'admin_templates/index.html', context)

@login_required(login_url=settings.LOGIN_URL, redirect_field_name='authentication_required')
def add_civilian_victim(request):
    success_message = ""

    if request.method == 'POST':
        civilian_model = Civilian_victims()
        civilian_model.author_id = request.user.pk
        civilian_model.full_name = request.POST.get('fullname')
        civilian_model.gender = request.POST.get('gender')
        civilian_model.age = request.POST.get('age') or None
        if request.FILES.get('photo'):
            civilian_model.picture = request.FILES.get('photo')
        else:
            if request.POST.get('gender') == 'Male':
                civilian_model.picture = "civilian_victims_pic/default.png"
            else:
                civilian_model.picture = "civilian_victims_pic/default_female.jpg"
        civilian_model.perpetrator = request.POST.get('perpetrator')
        woreda_obj = Tigray_woreda.objects.only(
            'woreda_name',
            'zone',
        ).get(woreda_name=request.POST.get('woreda'))
        civilian_model.woreda = woreda_obj
        civilian_model.zone = woreda_obj.zone
        civilian_model.place_of_killing = request.POST.get('place')
        civilian_model.date_of_event = request.POST.get('date_of_event') or None
        civilian_model.source = request.POST.get('source')
        civilian_model.source_link = request.POST.get('source_link')
        civilian_model.remark = request.POST.get('remark')

        previous_existed_civilian_victim = Civilian_victims.objects.filter(
            full_name=civilian_model.full_name,
            woreda=woreda_obj,
        ).order_by().only('id').first()

        civilian_model.approval = request.user.is_superuser
        civilian_model.save()

        if previous_existed_civilian_victim is not None:
            existing_victim_url = request.build_absolute_uri(
                reverse(
                    'view-victim-info',
                    kwargs={'id': previous_existed_civilian_victim.id},
                )
            )
            error_message = (
                'A civilian victim with the provided full name and Woreda '
                f'already exists. <a href="{existing_victim_url}" '
                'target="_blank"><u>Click here to view the existing '
                'victim</u></a>.'
            )
            return JsonResponse(
                {
                    'message': error_message,
                    'new_duplicate_id': civilian_model.id,
                },
                status=400,
            )

        if request.user.is_superuser:
            success_message = 'New civilian victim data added successfully.'
        else:
            success_message = (
                'New civilian victim data added successfully and is pending '
                'approval.'
            )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(
                {
                    'message': 'Success!',
                    'success_message': success_message,
                },
                status=200,
            )

    administrator = Administrator.objects.get(user=request.user)
    request.user._state.fields_cache["administrator"] = administrator
    context = {
        'pending_count': get_admin_pending_count(),
        'Administrator': administrator,
        'woreda_list': get_admin_civilian_woreda_names(),
        'success_message': success_message,
    }

    return render(request, 'admin_templates/civilian_victim/add_civilian_victim.html', context)

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def civilian_data_management(request):
    administrator = Administrator.objects.get(user=request.user)
    request.user._state.fields_cache["administrator"] = administrator
    context = {
        'pending_count': get_admin_pending_count(),
        'Administrator': administrator,
    }

    return render(request, 'admin_templates/civilian_victim/civilian_data_management.html', context)


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
@require_GET
def civilian_data_management_data(request):
    administrator = Administrator.objects.get(user=request.user)
    request.user._state.fields_cache["administrator"] = administrator
    if not (request.user.is_superuser or administrator.civilian_role):
        return JsonResponse(
            {"detail": "You do not have permission to access this data."},
            status=403,
        )
    return JsonResponse(build_civilian_management_payload(request))


@login_required(login_url=settings.LOGIN_URL, redirect_field_name='authentication_required')
@require_GET
def civilian_data_management_export(request, export_format):
    if not request.user.is_superuser:
        return JsonResponse(
            {"detail": "Only superusers can export civilian victim data."},
            status=403,
        )
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise Http404("Unsupported civilian export format.")
    return build_civilian_export_response(
        export_format,
        request.user,
        request.GET,
    )


@login_required(login_url=settings.LOGIN_URL, redirect_field_name='authentication_required')
@require_GET
def civilian_data_management_export_data(request):
    if not request.user.is_superuser:
        return JsonResponse(
            {"detail": "Only superusers can export civilian victim data."},
            status=403,
        )
    return JsonResponse(
        build_civilian_export_payload(request.user, request.GET)
    )


class Update_Civilian_Victim(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/civilian_victim/update_civilian_victim.html'
    model = Civilian_victims
    form_class = Civilian_Victim_Form
    success_message = 'Civilian victim informatiom updated successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Civilian_victims, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('civilian-data-management')

@login_required
def delete_duplicate_civilian_victim_item(request, pk):
    civilian_victim = get_object_or_404(Civilian_victims, id=pk)

    civilian_victim.delete()

    return redirect('admin-add-civilian')

class delete_civilian_victim_item(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/civilian_victim//delete_civilian_victim.html'
    model = Civilian_victims
    success_message = 'Civilian victim informatiom deleted successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Civilian_victims, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('civilian-data-management')

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Add_unverified_civilian(request):
    success_message = ''

    if request.method == 'POST':
        unverified_model = Unverified_civilian()
        unverified_model.location = request.POST.get('location')
        unverified_model.number_of_civilian = request.POST.get('number_of_civilian')
        unverified_model.perpetrator = request.POST.get('perpetrator')
        woreda_obj = Tigray_woreda.objects.only(
            'woreda_name',
            'zone',
        ).get(woreda_name=request.POST.get('woreda'))
        unverified_model.woreda = woreda_obj
        unverified_model.zone = woreda_obj.zone
        unverified_model.source = request.POST.get('source')
        unverified_model.source_link = request.POST.get('source_link')
        unverified_model.remark = request.POST.get('remark')

        unverified_model.save()

        # Add success message to context
        success_message = 'New unidentified civilian victims data added successfully.'

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # If the request is AJAX, return JSON response with success message
            return JsonResponse({'message': 'Success!', 'success_message': success_message}, status=200)

    administrator = Administrator.objects.get(user=request.user)
    request.user._state.fields_cache["administrator"] = administrator
    context = {
        'pending_count': get_admin_pending_count(),
        'Administrator': administrator,
        'woreda_list': get_admin_civilian_woreda_names(),
    }

    return render(request, 'admin_templates/civilian_victim/unverified_add_data.html', context)
    
@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Unverified_civilian_data_management(request):
    administrator = Administrator.objects.get(user=request.user)
    request.user._state.fields_cache["administrator"] = administrator

    context = {
        'pending_count': get_admin_pending_count(),
        'Administrator': administrator,
    }

    return render(request, 'admin_templates/civilian_victim/unverified_civilian_data_management.html', context)


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
@require_GET
def unverified_civilian_data_management_data(request):
    if not request.user.is_superuser:
        return JsonResponse(
            {"detail": "Only superusers can access this data."},
            status=403,
        )
    return JsonResponse(build_unverified_management_payload(request))


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
@require_GET
def unverified_civilian_data_management_export_data(request):
    if not request.user.is_superuser:
        return JsonResponse(
            {"detail": "Only superusers can export this data."},
            status=403,
        )
    return JsonResponse(build_unverified_export_payload(request.GET))


class Update_unverified_Civilian_Victim(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/civilian_victim/unverified_update_civilian_victim.html'
    model = Unverified_civilian
    form_class = Unverified_civilian_form
    success_message = 'Civilian victim informatiom updated successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Unverified_civilian, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('unverified-civilian-data-management')

@login_required
def delete_unverified_civilian_victim(request, pk):
    unverified_civilian_victim = get_object_or_404(Unverified_civilian, id=pk)

    unverified_civilian_victim.delete()

    # Add success message
    messages.success(request, 'Unverified civilian victim data has been successfully removed.')

    return redirect('unverified-civilian-data-management')


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Write_article(request):
    return _save_analysis_article(request, draft=False)



@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Draft_article(request):
    return _save_analysis_article(request, draft=True)


def _is_ajax_request(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _analysis_article_context(request, form):
    administrator = Administrator.objects.get(user=request.user)
    # The base template also accesses request.user.administrator. Reuse the
    # instance already fetched for the role checks instead of querying twice.
    request.user._state.fields_cache['administrator'] = administrator
    return {
        'pending_count': get_admin_pending_count(),
        'analysis_form': form,
        'Administrator': administrator,
    }


def _analysis_article_error_message(form):
    errors = []
    for field_name, field_errors in form.errors.items():
        label = form.fields[field_name].label if field_name in form.fields else field_name
        errors.extend(f'{label}: {error}' for error in field_errors)
    return '. '.join(errors) if errors else 'Please correct the highlighted fields.'


def _save_analysis_article(request, draft):
    form = AnalysisArticleForm(
        request.POST or None,
        request.FILES or None,
    )

    if request.method == 'POST':
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.approval = request.user.is_superuser
            article.draft = draft
            article.save()

            if draft:
                success_message = 'New analysis article saved to draft...'
            elif request.user.is_superuser:
                success_message = 'New analysis article shared successfully...'
            else:
                success_message = (
                    'New analysis article shared successfully and is pending '
                    'for an approval ...'
                )

            if _is_ajax_request(request):
                return JsonResponse({
                    'success': True,
                    'message': success_message,
                    'article_id': str(article.pk),
                })

            messages.success(request, success_message)
            return redirect('write-article')

        if _is_ajax_request(request):
            return JsonResponse({
                'success': False,
                'message': _analysis_article_error_message(form),
                'errors': form.errors.get_json_data(),
            }, status=400)

    return render(
        request,
        'admin_templates/analysis_article/write_article.html',
        _analysis_article_context(request, form),
    )


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Analysis_articles_management(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    analysis_articles = Analysis_articles.objects.filter(approval=True, draft=False)
    specfic_analysis_articles = Analysis_articles.objects.filter(
        author=request.user, draft = False)

    context = {
        'pending_count': pending_count,
        'analysis_articles': analysis_articles,
        'Administrator': Administrator.objects.get(user=request.user),
        'specfic_data': specfic_analysis_articles
    }

    return render(request, 'admin_templates/analysis_article/article_data_management.html', context)



@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Draft_articles_management(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    analysis_articles = Analysis_articles.objects.filter(author = request.user, draft=True)

    context = {
        'pending_count': pending_count,
        'analysis_articles': analysis_articles,
    }

    return render(request, 'admin_templates/analysis_article/draft_article_management.html', context)


class Update_Article_Analysis(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/analysis_article/update_analysis_article.html'
    model = Analysis_articles
    form_class = AnalysisArticleForm
    success_message = 'Analysis Article updated successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Analysis_articles, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('analysis-article-management')


class Update_Draft_Analysis(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/analysis_article/update_draft_article.html'
    model = Analysis_articles
    form_class = AnalysisArticleForm
    success_message = 'Draft Article updated successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Analysis_articles, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('analysis-article-management')
        
    def form_valid(self, form):
        if 'publish' in self.request.POST:  # Check if the "Publish" button was clicked
            instance = form.save(commit=False)
            instance.draft = False  # Set draft to False
            instance.save()
            return super().form_valid(form)
        else:
            return super().form_valid(form)


class Delete_Article_Analysis(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/analysis_article/delete_analysis_article.html'
    model = Analysis_articles
    success_message = 'Analysis Article deleted successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Analysis_articles, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('analysis-article-management')

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Add_webinar_discussion(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    form = Webinar_discussion_Form()

    context = {
        'pending_count': pending_count,
        'webinar_form': form
    }

    if request.method == 'POST':
        form = Webinar_discussion_Form(request.POST, request.FILES)
        if form.is_valid():
            insert_webinar = Webinar(author=User.objects.get(username=request.user), webinar_title=form.cleaned_data.get('webinar_title'),
                                            webinar_content=form.cleaned_data.get('webinar_content'),
                                            webinar_video_url=form.cleaned_data.get('webinar_video_url'))
            insert_webinar.save()

            messages.success(
                request, 'New webinar discussion shared successfully...')

        return render(request, 'admin_templates/analysis_article/add_webinar_discussion.html', context)

    else:
        return render(request, 'admin_templates/analysis_article/add_webinar_discussion.html', context)

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Webinar_discussion_management(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    webinar_discussion = Webinar.objects.all()

    context = {
        'pending_count': pending_count,
        'webinar_discussion': webinar_discussion
    }

    return render(request, 'admin_templates/analysis_article/webinar_data_management.html', context)


class Update_webinar_discussion(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/analysis_article/update_webinar_discussion.html'
    model = Webinar
    form_class = Webinar_discussion_Form
    success_message = 'Panel discussion updated successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Webinar, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('webinar-discussion-management')


class Delete_Webinar_discussion(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/analysis_article/delete_webinar_discussion.html'
    model = Webinar_discussion_Form
    success_message = 'Panel discussion deleted successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Webinar, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context 

    def get_success_url(self):

        return reverse('webinar-discussion-management')

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Archive_create_photo(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    context = {
        'pending_count': pending_count,
        'Administrator': Administrator.objects.get(user=request.user),
        'woreda_list': Tigray_woreda.objects.all(),
    }

    if request.method == 'POST':

        archive_model = Photo_archive()
        archive_model.author = User.objects.get(username=request.user)
        archive_model.location = request.POST.get('archive_location')
        woreda_obj = Tigray_woreda.objects.get(woreda_name = request.POST.get('archive_woreda'))
        archive_model.woreda = woreda_obj
        archive_model.date_of_event = request.POST.get('archive_date_of_event') or None
        archive_model.description = request.POST.get('archive_description')
        archive_model.photo = request.FILES.get('archive_photo')
        if request.POST.get('is_graphic'):
            archive_model.graphic = True

        archive_model.save()

        messages.success(
            request, 'New photo archive shared successfully...')

        return render(request, 'admin_templates/archive_templates/add_photo_archive.html', context)

    else:
        return render(request, 'admin_templates/archive_templates/add_photo_archive.html', context)

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Archive_manage_photo(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    photo_archive = Photo_archive.objects.all()

    context = {
        'pending_count': pending_count,
        'photo_archive': photo_archive,
        'Administrator': Administrator.objects.get(user=request.user)
    }

    return render(request, 'admin_templates/archive_templates/photo_archive_management.html', context)


class Update_photo_archive(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/archive_templates/update_photo_archive.html'
    model = Photo_archive
    form_class = Photo_Archive_Form
    success_message = 'Photo Archive updated successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Photo_archive, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('manage-photo-archive')


class Delete_photo_archive(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/archive_templates/delete_photo_archive.html'
    model = Photo_archive
    success_message = 'Photo Archive deleted successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Photo_archive, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('manage-photo-archive')

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Archive_create_video(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    context = {
        'pending_count': pending_count,
        'Administrator': Administrator.objects.get(user=request.user),
        'woreda_list': Tigray_woreda.objects.all(),
    }

    if request.method == 'POST':

        archive_model = Video_archive()
        archive_model.author = User.objects.get(username=request.user)
        archive_model.location = request.POST.get('archive_location')
        woreda_obj = Tigray_woreda.objects.get(woreda_name = request.POST.get('archive_woreda'))
        archive_model.woreda = woreda_obj
        archive_model.date_of_event = request.POST.get('archive_date_of_event') or None
        archive_model.description = request.POST.get('archive_description')
        archive_model.online_link = request.POST.get('online_link')

        archive_model.save()

        messages.success(
            request, 'New Video archive shared successfully...')

        return render(request, 'admin_templates/archive_templates/add_video_archive.html', context)

    else:
        return render(request, 'admin_templates/archive_templates/add_video_archive.html', context)


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Archive_manage_video(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    video_archive = Video_archive.objects.all()

    context = {
        'pending_count': pending_count,
        'video_archive': video_archive,
        'Administrator': Administrator.objects.get(user=request.user)
    }

    return render(request, 'admin_templates/archive_templates/video_archive_management.html', context)


class Update_video_archive(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/archive_templates/update_video_archive.html'
    model = Photo_archive
    form_class = Video_Archive_Form
    success_message = 'Video archive updated successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Video_archive, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('manage-video-archive')


class Delete_video_archive(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/archive_templates/delete_video_archive.html'
    model = Video_archive
    success_message = 'Video archive deleted successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Video_archive, id=id_)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('manage-video-archive')

@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Create_admin_account(request):

    # get available pending posts
    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    # generate random password for administrator
    ascii_alphabets = string.printable[:67]

    context = {
        'pending_count': pending_count,
        'Administrator': Administrator.objects.get(user=request.user)
    }

    administrator_model = Administrator()

    if request.method == 'POST':

        check_username = User.objects.filter(
            username=request.POST.get('admin_username'))

        if not check_username:

            
            random_andom_password = ''
            for i in range(0, 8):
                random_andom_password += random.choice(ascii_alphabets)

            first_name = request.POST.get('admin_first_name')
            last_name = request.POST.get('admin_last_name')
            email = request.POST.get('admin_email')
            username = request.POST.get('admin_username')
            password = make_password(random_andom_password)

            if request.POST.get('super_admin'):
                is_superuser = True
            else:
                is_superuser = False

            email_subject = "Your System Administration Account Created Successfully"
            email_body = '''
                <!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Transitional //EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office"
    xmlns:v="urn:schemas-microsoft-com:vml" lang="en">

<head>
    <link rel="stylesheet" type="text/css" hs-webfonts="true"
        href="https://fonts.googleapis.com/css?family=Lato|Lato:i,b,bi">
    <title>Email template</title>
    <meta property="og:title" content="Email template">

    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

    <meta http-equiv="X-UA-Compatible" content="IE=edge">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">


</head>

<body bgcolor="#F5F8FA"
    style="width: 100%; margin: auto 0; padding:0; font-family:Lato, sans-serif; font-size:18px; color:#33475B; word-break:break-word">

    <! View in Browser Link -->

        <div id="email" style="margin: auto;
        width: 600px;
        background-color: white;">
            <table align="right" role="presentation">
                <tr>
                    <td style="vertical-align: top;">
                        <a class="subtle-link" style="text-decoration: underline;
        color: inherit;
        font-weight: bold;
        color: #253342; font-size: 9px; 
        text-transform:uppercase; 
        letter-spacing: 1px;
        color: #CBD6E2;" href="#">View in Browser</a>
                    </td>
                <tr>
            </table>


            <! Banner -->
                <table role="presentation" width="100%">
                    <tr>

                        <td bgcolor="black" align="center" style="color: white;vertical-align: top;">

                            <h3><i>System Admin Account </h3>

                        </td>
                </table>




                <! First Row -->

                    <table role="presentation" border="0" cellpadding="0" cellspacing="10px"
                        style="padding: 30px 30px 30px 60px;">
                        <tr>
                            <td style="vertical-align: top;">
                                <p style="font-weight: 100;">
                                    Your system administration account has been created successfully.
                                </p>
                                <ul>
                                    <li>
                                        <p style="text-weight: normal; font-weight: 100;">🔐 Username: <b
                                                style="color: blue">{}</b></p>
                                    </li>
                                    <li>
                                        <p style="text-weight: normal; font-weight: 100;">🔐 Password: <b
                                                style="color: blue">{}</b></p>
                                    </li>

                                </ul>
                                <p>👉 You can change your username and password once you log in with this one.</p>
                                <br>
                                <div style="text-align: center">
                                    <a href="www.tigraygenocide.com/Adminstrator-login-page/">
                                        <button style="font: inherit;
        background-color: #FF7A59;
        border: none;
        padding: 10px;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 900; 
        color: white;
        border-radius: 5px; 
        box-shadow: 3px 3px #d94c53;">
                                        Sign in to your account.
                                    </button>
                                    </a>
                                </div>
                            </td>
                        </tr>
                    </table>

                    <! Banner Row -->
                        <table role="presentation" bgcolor="#EAF0F6" width="100%" style="margin-top: 50px;">
                            <tr>
                                <td align="center" style="padding: 30px 30px;">

                                    <h2 style="font-size: 28px;
        font-weight: 900; "> Tigray Genocide </h2>
                                    <p style="font-weight: 100; text-decoration: none">
                                        www.tigraygenocide.com

                                    </p>
                                </td>
                            </tr>
                        </table>

        </div>
</body>

</html>
            '''.format(username, random_andom_password)
            
            email_from = settings.EMAIL_HOST_USER
            email_to = [email]

            msg = EmailMessage(email_subject, email_body, email_from, email_to)
            msg.content_subtype = "html"  # Set the content type to HTML

            # Send the email
            msg.send()

            admin = User.objects.create(first_name=first_name, last_name=last_name,
                                        email=email, username=username, password=password, is_staff=is_superuser, is_superuser=is_superuser)

            admin.save()

            get_admin_obj = User.objects.get(username=username)

            # send account email to the user
            # get_admin_obj.email_user(
            #         'Your System Administration Account Created Successfully',
            #         f'<h5>Username: <span style="colore:red">{username}</span></h5><p>This is a paragraph.</p>',
            #         'eminemmerne@gmail.com'
            #     )
                
            # save admin permission

            administrator_model.user = get_admin_obj

            if request.POST.get('civilian_victim_role'):
                administrator_model.civilian_role = True
            if request.POST.get('analysis_article_role'):
                administrator_model.analysis_role = True

            administrator_model.save()

            messages.success(
                request, 'New admin account created successfully...')

        else:

            messages.error(
                request, 'Username available...')

        return render(request, 'admin_templates/account_templates/create_account.html', context)

    else:

        return render(request, 'admin_templates/account_templates/create_account.html', context)


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Manage_admin_account(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    context = {
        'pending_count': pending_count,
        'is_notsuperuser': User.objects.filter(is_superuser=False, is_active=True)
    }

    return render(request, 'admin_templates/account_templates/account_management.html', context)

class Update_admin_permissions(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/account_templates/update_admin_permission.html'
    model = Administrator
    form_class = Administrator_form
    success_message = 'Account permission successfully changed'

    def get_object(self, *args, **kwargs):
        get_id = self.kwargs.get('admin_id')
        return get_object_or_404(Administrator, user=User.objects.get(id = get_id))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('manage-admin-account')
        
@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Deactivate_admin_account(request, admin_id):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    context = {
        'pending_count': pending_count,
    }

    user_model = User.objects.get(id = admin_id)

    if request.method == 'POST':
        user_model.is_active = False
        user_model.save()

        messages.success(request, 'Admin account removed successfully')

        return redirect('/Manage-admin-account/')

    return render(request, 'admin_templates/account_templates/deactivate_admin_account.html', context)

        
@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Pending_posts_management(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    pending_civilian_victims = Civilian_victims.objects.filter(approval=False)
    pending_analysis_articles = Analysis_articles.objects.filter(
        approval=False, draft=False)

    context = {
        'pending_count': pending_count,
        'pending_civilian_victims': pending_civilian_victims,
        'pending_analysis_articles': pending_analysis_articles
    }

    return render(request, 'admin_templates/pending_templates/pending.html', context)


class Approve_Civilian_Victim(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/pending_templates/approve_civilian_victim.html'
    model = Civilian_victims
    form_class = Approve_Civilian_Victim_Form
    success_message = 'Civilian victim informatiom approved successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Civilian_victims, id=id_, approval=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('pending-posts-management')


class Approve_Article_Analysis(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    redirect_field_name = '/authentication_required/'
    template_name = 'admin_templates/pending_templates/approve_analysis_articles.html'
    model = Analysis_articles
    form_class = Approve_Analysis_Form
    success_message = 'Analysis article approved successfully'

    def get_object(self, *args, **kwargs):
        id_ = self.kwargs.get('pk')
        return get_object_or_404(Analysis_articles, id=id_, approval=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['Administrator'] = Administrator.objects.get(
            user=self.request.user)
        context['pending_count'] = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()
        return context

    def get_success_url(self):

        return reverse('pending-posts-management')


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Account_settings(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    current_user = User.objects.get(username = request.user.username)

    context = {
        'pending_count': pending_count,
        'Administrator': Administrator.objects.get(user=request.user),
        'webinar_password': Webmail_password_manager.objects.all().count()
    }

    if request.method == 'POST':
        current_user.first_name = request.POST['new_first_name']
        current_user.last_name = request.POST['new_last_name']
        current_user.username = request.POST['new_username']
        current_user.save()
        messages.success(request, 'Account Updated Successfully')

        return redirect('/Account-settings/')

    return render(request, 'admin_templates/admin_settings/settings.html', context)


@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Password_settings(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    current_user = User.objects.get(username = request.user.username)

    context = {
        'pending_count': pending_count,
        'Administrator': Administrator.objects.get(user=request.user)
    }

    if request.method == 'POST':
        is_valid_password = current_user.check_password(request.POST['old_password'])
        if is_valid_password:
            if request.POST['new_password'] == request.POST['confirm_new_password']:
                # Update the user's password
                current_user.set_password(request.POST['new_password'])
                current_user.save()
                messages.success(request, 'Password has been successfully changed')
            else:
                messages.error(request, 'New password and confirm password does not match')
        else:
            messages.error(request, 'Old password is not correct')

        return redirect('/Account-settings/')

    return render(request, 'admin_templates/admin_settings/settings.html', context)



@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Profile_picture_settings(request):

    pending_count = Civilian_victims.objects.filter(approval = False).count() + Analysis_articles.objects.filter(approval=False, draft=False).count()

    current_user = User.objects.get(username = request.user.username)
    current_admin_profile = Administrator.objects.get(user = current_user)

    context = {
        'pending_count': pending_count,
        'Administrator': Administrator.objects.get(user=request.user)
    }

    if request.method == 'POST':
        current_admin_profile.admin_photo = request.FILES.get('new_profile_picture')
        current_admin_profile.save()

        messages.success(request, 'Profile picture has been successfully changed')

        return redirect('/Account-settings/')

    return render(request, 'admin_templates/admin_settings/settings.html', context)



@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def Webmail_password_setting(request):

    if request.method == 'POST':
        
        if Webmail_password_manager.objects.all().count() > 0:
            get_first_row = Webmail_password_manager.objects.first()
            if get_first_row.password == request.POST.get("old_webmail_password"):
                if request.POST.get("new_webmail_password") == request.POST.get("confirm_webmail_password"):
                    get_first_row.password = request.POST.get("new_webmail_password")
                    get_first_row.save()
                    messages.success(request, 'Webmail password updated successfully!')
            
                    return redirect('/Account-settings/')
                else:
                    messages.error(request, 'New password doesn\'t match!')
            
                    return redirect('/Account-settings/')
                    
            else:
                messages.error(request, 'Old webinar password is not correct!')
        
                return redirect('/Account-settings/')
        else:
            Webmail_password_manager.objects.create(password = request.POST.get("new_webmail_password"))

            messages.success(request, 'Webmail password saved successfully!')
    
            return redirect('/Account-settings/')

    return render(request, 'admin_templates/admin_settings/settings.html', context)
    
# export database SQL backup
@login_required(login_url='/Adminstrator-login-page', redirect_field_name='authentication_required')
def export_database(request):
    # Database credentials
    db_name = settings.DATABASES['default']['NAME']
    db_user = settings.DATABASES['default']['USER']
    db_password = settings.DATABASES['default']['PASSWORD']

    # Get current date
    current_date = datetime.now().strftime('%m-%d-%Y')

    # Specify the file path where you want to save the SQL dump
    filename = f'database-Backup-{current_date}.sql'
    filepath = os.path.join(settings.BASE_DIR, filename)

    # Command to export MySQL database using mysqldump
    command = f"mysqldump -u {db_user} -p{db_password} {db_name} > {filepath}"

    try:
        # Execute the command
        subprocess.run(command, shell=True, check=True)
        with open(filepath, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/sql')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except subprocess.CalledProcessError as e:
        return HttpResponse(f"Error exporting database: {e}", status=500)
