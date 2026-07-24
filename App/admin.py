from django.contrib import admin
from django.utils.html import format_html
from .models import Civilian_victims
from .models import Unverified_civilian
from .models import Analysis_articles
from .models import Article_comments
from .models import Webinar
from .models import Photo_archive
from .models import Video_archive
from .models import Administrator
from .models import Tigray_woreda
from .models import Hero_images
from .models import Webmail_password_manager
from import_export import resources
from import_export.admin import ImportExportModelAdmin
# Summernote
from django_summernote.models import Attachment
from django_summernote.admin import SummernoteModelAdmin

admin.site.site_header = "TigrayGenocide"
admin.site.site_title = "TigrayGenocide Admin"
admin.site.index_title = "TigrayGenocide Administration Panel"

class CivilianVictimsResource(resources.ModelResource):
    class Meta:
        model = Civilian_victims
        
@admin.register(Civilian_victims)
class CivilianVictimsAdmin(ImportExportModelAdmin):
    resource_class = CivilianVictimsResource
    
    list_display = (
        "full_name",
        "gender",
        "age",
        "zone",
        "woreda",
        "place_of_killing",
        "perpetrator",
        "date_of_event",
        "date_created",
    )

    list_filter = (
        "gender",
        "zone",
        "woreda",
        "perpetrator",
        "date_created",
    )

    search_fields = (
        "full_name",
        "place_of_killing",
        "zone",
        "woreda__woreda_name",
        "source",
    )

    readonly_fields = ("picture_preview", "date_created")

    ordering = ("-date_created",)

    fields = (
        "sender_fullname",
        "sender_location",
        "sender_email",
        "sender_phone",
        "author",
        "full_name",
        "gender",
        "place_of_killing",
        "age",
        "woreda",
        "zone",
        "source",
        "source_link",
        "perpetrator",
        "date_of_event",
        "remark",
        "picture",
        "picture_preview",
        "approval",
        "date_created",
    )

    def picture_preview(self, obj):
        if not obj.pk or not obj.picture:
            return "No image uploaded."
        return format_html(
            '<img src="{}" alt="Victim picture preview" style="max-height: 220px; max-width: 320px; border-radius: 6px;" />',
            obj.picture.url,
        )
    picture_preview.short_description = "Preview"
    
# Resource for import/export functionality
class UnverifiedCivilianResource(resources.ModelResource):
    class Meta:
        model = Unverified_civilian

# Admin configuration
@admin.register(Unverified_civilian)
class UnverifiedCivilianAdmin(ImportExportModelAdmin):
    resource_class = UnverifiedCivilianResource

    list_display = (
        "location",
        "number_of_civilian",
        "perpetrator",
        "zone",
        "woreda",
        "source",
        "date_created",
    )

    list_filter = (
        "perpetrator",
        "zone",
        "woreda",
        "date_created",
    )

    search_fields = (
        "location",
        "zone",
        "woreda__woreda_name",
        "source",
    )

    readonly_fields = ("date_created",)

    ordering = ("-date_created",)

class PhotoArchiveResource(resources.ModelResource):
    class Meta:
        model = Photo_archive

@admin.register(Photo_archive)
class PhotoArchiveAdmin(ImportExportModelAdmin):
    resource_class = PhotoArchiveResource

    list_display = (
        "location",
        "woreda",
        "date_of_event",
        "date_created",
    )

    list_filter = (
        "woreda",
        "date_of_event",
        "date_created",
        "graphic",
    )

    search_fields = (
        "location",
        "description",
        "woreda__woreda_name",
    )

    readonly_fields = ("photo_preview", "date_created")

    fields = (
        "author",
        "location",
        "woreda",
        "date_of_event",
        "description",
        "photo",
        "photo_preview",
        "graphic",
        "date_created",
    )

    ordering = ("-date_created",)

    def photo_preview(self, obj):
        if not obj.pk or not obj.photo:
            return "No image uploaded."
        return format_html(
            '<img src="{}" alt="Photo archive preview" style="max-height: 220px; max-width: 320px; border-radius: 6px;" />',
            obj.photo.url,
        )
    photo_preview.short_description = "Preview"
    
@admin.register(Analysis_articles)
class AnalysisArticlesAdmin(SummernoteModelAdmin):
    list_display = (
        'short_title',
        'author',
        'formatted_date_created',
        'endf_related',
        'personal_account',
        'approval',
        'draft',
    )
    
    ordering = ('-date_created',)
    search_fields = ('title', 'content', 'author__username')
    list_filter = ('endf_related', 'personal_account', 'approval', 'draft', 'date_created')
    list_per_page = 10

    summernote_fields = ('content',)  # enable Summernote for 'content'

    exclude = ('id', 'date_created')  # hide UUID and date_created from form

    # -----------------------
    # Custom display functions
    # -----------------------
    def short_title(self, obj):
        return obj.title[:40] + ('...' if len(obj.title) > 40 else '')
    short_title.short_description = 'Title'

    def formatted_date_created(self, obj):
        return obj.date_created.strftime('%d %b, %Y')
    formatted_date_created.short_description = 'Created At'
    
admin.site.register(Article_comments)
admin.site.register(Webinar)
admin.site.register(Video_archive)
admin.site.register(Administrator)
admin.site.register(Tigray_woreda)
admin.site.register(Hero_images)
admin.site.register(Webmail_password_manager)
