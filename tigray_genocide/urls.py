"""

URL configuration for tigray_genocide project.



The `urlpatterns` list routes URLs to views. For more information please see:

    https://docs.djangoproject.com/en/4.2/topics/http/urls/

Examples:

Function views

    1. Add an import:  from my_app import views

    2. Add a URL to urlpatterns:  path('', views.home, name='home')

Class-based views

    1. Add an import:  from other_app.views import Home

    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')

Including another URLconf

    1. Import the include() function: from django.urls import include, path

    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))

"""

from django.contrib import admin

from django.conf.urls.static import static

from django.conf import settings

from django.urls import path, include

from django.contrib.auth.views import PasswordResetView

from django.contrib.auth.views import PasswordResetDoneView

from django.contrib.auth.views import PasswordResetConfirmView

from django.contrib.auth.views import PasswordResetCompleteView

from App.views import index

# civilian victim views

from django.conf.urls import handler404

from App.views import custom_404_view

from App.views import civilian_victims_by_name

from App.views import view_victim_info

from App.views import Civilian_victim_photo_page

from App.views import Search_civilian

from App.views import Civilian_victim_by_map

from App.views import Civilian_victim_by_map_info

from App.views import unverified_civilian_victims_by_name

# artcile views

from App.views import View_article

from App.views import Article_comment

from App.views import Articles_page

from App.views import General_category_articles

from App.views import Search_article

from App.views import Webinar_discussion_page

from App.views import View_webinar_discussion

# archive views

from App.views import Archive_photo

from App.views import Search_archive_photo

from App.views import Archive_video

from App.views import Watch_video

# user message views

from App.views import Send_us_information

from App.views import Send_archive

from App.views import About_us

from App.views import Contact_us

""" admin views url pattern """

# admin authentication views

from App.views import Admin_login

from App.views import Admin_logout

from App.views import admin_dashboard

# admin civilian victim views

from App.views import admin_civilian_victims_page

from App.views import add_civilian_victim

from App.views import civilian_data_management

from App.views import civilian_data_management_data

from App.views import delete_civilian_victim_item

from App.views import delete_duplicate_civilian_victim_item

from App.views import Update_Civilian_Victim

from App.views import Add_unverified_civilian

from App.views import Unverified_civilian_data_management

from App.views import Update_unverified_Civilian_Victim

from App.views import delete_unverified_civilian_victim

from App.views import export_unverified_data

# analysis articles views

from App.views import Write_article

from App.views import Draft_article

from App.views import Draft_articles_management

from App.views import Analysis_articles_management

from App.views import Update_Article_Analysis

from App.views import Update_Draft_Analysis

from App.views import Delete_Article_Analysis

from App.views import Add_webinar_discussion

from App.views import Webinar_discussion_management

from App.views import Update_webinar_discussion

from App.views import Delete_Webinar_discussion

# admin archive views

from App.views import Archive_create_photo

from App.views import Archive_manage_photo

from App.views import Update_photo_archive

from App.views import Delete_photo_archive

from App.views import Archive_create_video

from App.views import Archive_manage_video

from App.views import Update_video_archive

from App.views import Delete_video_archive

# admin account views

from App.views import Create_admin_account

from App.views import Manage_admin_account

from App.views import Update_admin_permissions

from App.views import Deactivate_admin_account

from App.views import Pending_posts_management

from App.views import Approve_Civilian_Victim

from App.views import Approve_Article_Analysis

from App.views import Account_settings

from App.views import Password_settings

from App.views import Profile_picture_settings

from App.views import Webmail_password_setting

from App.views import export_database



urlpatterns = [

    path('admin/', admin.site.urls),

    path('captcha/', include('captcha.urls')),

    path('reset-password/', PasswordResetView.as_view(template_name = 'admin_templates/account_templates/reset_password.html'), name = 'reset_password'),

    path('reset-password-sent/', PasswordResetDoneView.as_view(template_name = 'admin_templates/account_templates/reset_password_sent.html'), name = 'password_reset_done'),

    path('reset-password/<uidb64>/<token>', PasswordResetConfirmView.as_view(template_name = 'admin_templates/account_templates/reset.html'), name = 'password_reset_confirm'),

    path('reset-password-complete/', PasswordResetCompleteView.as_view(template_name = 'admin_templates/account_templates/reset_password_confirm.html'), name = 'password_reset_complete'),

    # summernote url pattern

    path('summernote/', include('django_summernote.urls')),

    # user page urls

    path('', index, name = 'app-index'),

    # civilian victim views

    path('Civilian-victims-by-name/', civilian_victims_by_name, name = 'civilian_victims_by_name'),

    path('View-victim-info/<slug:id>', view_victim_info, name = 'view-victim-info'),

    path('Civilina-victims-photo/', Civilian_victim_photo_page, name = 'civilian-victim-photo-page'),

    path('search-civilian-victim/', Search_civilian, name = 'search-civilian-victim'),

    path('Civilina-victims-location', Civilian_victim_by_map, name = 'civilian-victim-map-page'),

    path('Civilina-victims-location-information/<str:woreda_pr>', Civilian_victim_by_map_info, name = 'civilian-victim-map-info-page'),

    path('Unverified-Civilina-victims', unverified_civilian_victims_by_name, name = 'unverified-civilian-victim'),

    # analysis articles url pattern

    path('Articles-page/', Articles_page, name = 'app-articles-page'),

    path('Article-category/<slug:category>', General_category_articles, name = 'article-category'),

    path('View-article/<slug:id>', View_article, name = 'view-article'),

    path('Article-comment/<slug:article_id>', Article_comment, name = 'article-comment'),

    path('Searched-articles/', Search_article, name = 'search-articles-page'),

    path('Webinar-discussion-page', Webinar_discussion_page, name = 'webinar-discussion-page'),

    path('View-panel-discussion/<slug:id>', View_webinar_discussion, name = 'view-webinar-discussion'),

    # archive url pattern

    path('Archive-photo/', Archive_photo, name = 'archive-photo'),

    path('Search-archive-photo/', Search_archive_photo, name = 'search-archive-photo'),

    path('Archive-video/', Archive_video, name = 'archive-video'),

    path('Watch-video/<slug:id>', Watch_video, name = 'watch-video'),

    # user message url-pattern

    path('Send-information/', Send_us_information, name = 'send-information'),
    
    path('Send-archive/', Send_archive, name = 'send-archive'),

    # about us page

    path('About-us/', About_us, name = 'about-us'),

    # contact Us page

    path('Contact-us/', Contact_us, name = 'contact-us'),

    # admin view-url pattern

    # admin authentication url pattern

    path('Adminstrator-login-page/', Admin_login, name = 'admin-login'),

    path('Admin-logout/', Admin_logout, name = 'admin-logout'),

    path('Admin-dashboard/', admin_dashboard, name = 'admin-dashboard'),

    # admin civilian victims url-pattern

    path('Civilian-victims/', admin_civilian_victims_page, name = 'admin-civilian-victims'),

    path('Add-civilian-victim/', add_civilian_victim, name = 'admin-add-civilian'),

    path('Civilian-data-management/', civilian_data_management, name = 'civilian-data-management'),

    path('Civilian-data-management/data/', civilian_data_management_data, name = 'civilian-data-management-data'),

    path('Delete-duplicate-civilian-victim/<slug:pk>', delete_duplicate_civilian_victim_item, name = 'delete-duplicate-civilian-victim'),

    path('Delete-civilian-victim/<slug:pk>', delete_civilian_victim_item.as_view(), name = 'delete-civilian-victim'),

    path('Update-civilian-victim/<slug:pk>', Update_Civilian_Victim.as_view(), name = 'update-civilian-victim'),

    path('Add-unverified-civilian-data', Add_unverified_civilian, name = 'add-unverified-civilian'),

    path('Unverified-civilian-data-management/', Unverified_civilian_data_management, name = 'unverified-civilian-data-management'),

    path('Update-unverified-civilian-victim/<slug:pk>', Update_unverified_Civilian_Victim.as_view(), name = 'update-unverified-civilian-victim'),

    path('Delete-unverified-civilian-victim/<slug:pk>', delete_unverified_civilian_victim, name = 'delete-unverified-civilian-victim'),

    path('export-unverified-data', export_unverified_data, name = 'export-unverified-data'),

    # analysis articles url-pattern

    path('Write-article/', Write_article, name = 'write-article'),

    path('Draft-article/', Draft_article, name = 'draft-article'),

    path('Article-data-management/', Analysis_articles_management, name = 'analysis-article-management'),

    path('Draft-data-management/', Draft_articles_management, name = 'draft-article-management'),

    path('Update-analysis-article/<slug:pk>', Update_Article_Analysis.as_view(), name = 'update-analysis-article'),

    path('Update-draft-article/<slug:pk>', Update_Draft_Analysis.as_view(), name = 'update-draft-article'),

    path('Delete-analysis-article/<slug:pk>', Delete_Article_Analysis.as_view(), name = 'delete-analysis-article'),

    path('Add-webinar-discussion/', Add_webinar_discussion, name = 'add-webinar-discussion'),

    path('Webinar-data-management/', Webinar_discussion_management, name = 'webinar-discussion-management'),

    path('Update-webinar-discussion/<slug:pk>', Update_webinar_discussion.as_view(), name = 'update-webinar-discussion'),

    path('Delete-webinar-discussion/<slug:pk>', Delete_Webinar_discussion.as_view(), name = 'delete-webinar-discussion'),

    # admin archive url-pattern

    path('Add-photo-archive/', Archive_create_photo, name = 'add-photo-archive'),

    path('Photo-archive-management/', Archive_manage_photo, name = 'manage-photo-archive'),

    path('Update-photo-archive/<slug:pk>', Update_photo_archive.as_view(), name = 'update-photo-archive'),

    path('Delete-photo-archive/<slug:pk>', Delete_photo_archive.as_view(), name = 'Delete-photo-archive'),

    path('Video-archive-management/', Archive_manage_video, name = 'manage-video-archive'),

    path('Update-video-archive/<slug:pk>', Update_video_archive.as_view(), name = 'update-video-archive'),

    path('Delete-video-archive/<slug:pk>', Delete_video_archive.as_view(), name = 'Delete-video-archive'),

    path('Add-video-archive/', Archive_create_video, name = 'add-video-archive'),

    # admin account management url-pattern

    path('Create-admin-account/', Create_admin_account, name = 'create-admin-account'),

    path('Manage-admin-account/', Manage_admin_account, name = 'manage-admin-account'),

    path('Update-permissions/<slug:admin_id>', Update_admin_permissions.as_view(), name = 'update-admin-permissions'),

    path('Deativate-admin-account/<slug:admin_id>', Deactivate_admin_account, name = 'deactivate-admin-account'),

    path('Pending-posts-management/', Pending_posts_management, name = 'pending-posts-management'),

    path('Approve-civilian-victim-information/<slug:pk>', Approve_Civilian_Victim.as_view(), name = 'approve-civilian-victim'),

    path('Approve-analysis-articles/<slug:pk>', Approve_Article_Analysis.as_view(), name = 'approve-analysis-articles'),

    path('Account-settings/', Account_settings, name = 'account-settings'),

    path('Password-settings/', Password_settings, name = 'password-settings'),

    path('Profile-picture-settings/', Profile_picture_settings, name = 'profile-picture-settings'),
    
    path('webmail-password-settings/', Webmail_password_setting, name = 'webmail-password-settings'),
    
    path('export_database/', export_database, name = 'export-database')

] + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)

handler404 = custom_404_view
