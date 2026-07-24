# yourapp/sitemaps.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Civilian_victims, Analysis_articles

class CivilianVictimsSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Civilian_victims.objects.filter(approval=True)

    def location(self, obj):
        return reverse('view-victim-info', kwargs={'id': obj.id})


class AnalysisArticlesSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return Analysis_articles.objects.filter(approval=True, draft=False)

    def location(self, obj):
        return reverse('view-article', kwargs={'id': obj.id})
        
google-site-verification: google979a5b60db85004b.html