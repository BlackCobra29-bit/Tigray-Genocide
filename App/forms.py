from django.forms import ModelForm
from .models import Civilian_victims
from .models import Analysis_articles
from .models import Webinar
from .models import Photo_archive
from .models import Video_archive
from .models import Administrator
from .models import Tigray_woreda
from .models import Unverified_civilian
from django import forms
from froala_editor.widgets import FroalaEditor
from django.utils import timezone
from django.utils import timezone
from captcha.fields import CaptchaField
# Summernote
from django_summernote.widgets import SummernoteWidget

class LoginCaptchaForm(forms.Form):
    captcha = CaptchaField()

class Civilian_Victim_Form(ModelForm):
    class Meta:
        model = Civilian_victims
        fields = ['sender_fullname', 'sender_location', 'sender_email', 'sender_phone',
                 'full_name', 'age', 'gender', 'perpetrator', 'place_of_killing', 
                  'woreda', 'date_of_event', 'source', 'source_link', 'remark', 'picture', 'approval']
        widgets = {
            'sender_fullname': forms.TextInput(attrs={'class': 'form-control'}),
            'sender_location': forms.TextInput(attrs={'class': 'form-control'}),
            'sender_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'sender_phone': forms.TextInput(attrs={'class': 'form-control', 'type': 'tel'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'age': forms.NumberInput(attrs={'class': 'form-control'}),
            'perpetrator': forms.Select(attrs={'class': 'form-control'}),
            'place_of_killing': forms.TextInput(attrs={'class': 'form-control'}),
            'woreda': forms.Select(attrs={'class': 'selectpicker form-control'}),
            'date_of_event': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'source': forms.TextInput(attrs={'class': 'form-control'}),
            'source_link': forms.TextInput(attrs={'class': 'form-control'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
        } 

    def save(self, commit=True):
        instance = super().save(commit=False)
        gender = self.cleaned_data.get('gender')
        if self.cleaned_data.get('picture') == 'civilian_victims_pic/default.png' or self.cleaned_data.get('picture') == 'civilian_victims_pic/default_female.jpg':
            if gender == 'Male':
              instance.picture = 'civilian_victims_pic/default.png'
            else:
              instance.picture = "civilian_victims_pic/default_female.jpg"
        instance.zone = Tigray_woreda.objects.get(woreda_name = self.cleaned_data.get('woreda')).zone
        if commit:
            instance.save()
        return instance

class Approve_Civilian_Victim_Form(ModelForm):
    class Meta:
        model = Civilian_victims
        fields = ['sender_fullname', 'sender_location', 'sender_email', 'sender_phone',
                 'full_name', 'age', 'gender', 'perpetrator', 'place_of_killing', 
                  'woreda', 'date_of_event', 'source', 'source_link', 'remark', 'picture', 'approval']
        widgets = {
            'sender_fullname': forms.TextInput(attrs={'class': 'form-control'}),
            'sender_location': forms.TextInput(attrs={'class': 'form-control'}),
            'sender_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'sender_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'age': forms.NumberInput(attrs={'class': 'form-control'}),
            'perpetrator': forms.Select(attrs={'class': 'form-control'}),
            'place_of_killing': forms.TextInput(attrs={'class': 'form-control'}),
            'woreda': forms.Select(attrs={'class': 'selectpicker form-control'}),
            'date_of_event': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'source': forms.TextInput(attrs={'class': 'form-control'}),
            'source_link': forms.TextInput(attrs={'class': 'form-control'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
        }          

    def save(self, commit=True):
        instance = super().save(commit=False)
        gender = self.cleaned_data.get('gender')
        if self.cleaned_data.get('picture') == 'civilian_victims_pic/default.png' or self.cleaned_data.get('picture') == 'civilian_victims_pic/default_female.jpg':
            if gender == 'Male':
              instance.picture = 'civilian_victims_pic/default.png'
            else:
              instance.picture = "civilian_victims_pic/default_female.jpg"
        instance.date_created = timezone.now()
        instance.zone = Tigray_woreda.objects.get(woreda_name = self.cleaned_data.get('woreda')).zone
        instance.approval = True
        if commit:
            instance.save()
        return instance

class AnalysisArticleForm(forms.ModelForm):
    class Meta:
        model = Analysis_articles
        fields = [
            'title',
            'thumbnail',
            'content',
            'endf_related',
            'personal_account',
            'approval',
            'draft'
        ]

        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Article title',
                    'required': 'required',
                    'id': 'title-input'
                }
            ),
            'thumbnail': forms.ClearableFileInput(
                attrs={
                    'class': 'form-control',
                    'id': 'thumbnail-input'
                }
            ),
            'content': SummernoteWidget(),  # WYSIWYG editor
            'endf_related': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'personal_account': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'draft': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional: Customize labels
        self.fields['title'].label = 'Title'
        self.fields['thumbnail'].label = 'Thumbnail'
        self.fields['content'].label = 'Content'
        self.fields['endf_related'].label = 'ENDF Related'
        self.fields['personal_account'].label = 'Personal Account'
        self.fields['approval'].label = 'Approval'
        self.fields['draft'].label = 'Draft'

class Webinar_discussion_Form(forms.ModelForm):
  class Meta:
    model = Webinar
    fields = ['webinar_title', 'webinar_content', 'webinar_video_url']
    widgets = {
      'webinar_title': forms.Textarea(attrs={'class': 'form-control', 'rows': '2'}),
      'webinar_video_url': forms.TextInput(attrs={'class': 'form-control'}),
    }

class Approve_Analysis_Form(forms.ModelForm):
  class Meta:
    model = Analysis_articles
    fields = ['title', 'thumbnail', 'content', 'endf_related', 'personal_account', 'approval']
    widgets = {
      'title': forms.Textarea(attrs={'class': 'form-control', 'rows': '2'})
    }      

  def save(self, commit=True):
      instance = super().save(commit=False)
      instance.approval = True
      instance.date_created = timezone.now()
      if commit:
          instance.save()
      return instance

class Photo_Archive_Form(forms.ModelForm):
  class Meta:
    model = Photo_archive
    fields = ['location', 'woreda', 'date_of_event', 'description', 'photo', 'graphic']
    widgets = {
      'location': forms.TextInput(attrs={'class': 'form-control'}),
      'woreda': forms.Select(attrs={'class': 'selectpicker form-control'}),
      'date_of_event': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
      'description': forms.Textarea(attrs={'class': 'form-control', 'rows': '3'})
    }

class Video_Archive_Form(forms.ModelForm):
  class Meta:
    model = Video_archive
    fields = ['location', 'woreda', 'date_of_event', 'description', 'online_link', 'description']
    widgets = {
      'location': forms.TextInput(attrs={'class': 'form-control'}),
      'woreda': forms.Select(attrs={'class': 'selectpicker form-control'}),
      'date_of_event': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
      'online_link': forms.TextInput(attrs={'class': 'form-control'}),
      'description': forms.Textarea(attrs={'class': 'form-control', 'rows': '3'})
    }
    
class Unverified_civilian_form(forms.ModelForm):
  class Meta:
    model = Unverified_civilian
    fields = ['location', 'number_of_civilian', 'perpetrator', 'woreda', 'source', 'source_link', 'remark']
    widgets = {
      'location': forms.TextInput(attrs={'class': 'form-control'}),
      'number_of_civilian': forms.NumberInput(attrs={'class': 'form-control'}),
      'perpetrator': forms.Select(attrs={'class': 'form-control'}),
      'woreda': forms.Select(attrs={'class': 'selectpicker form-control'}),
      'source': forms.TextInput(attrs={'class': 'form-control'}),
      'source_link': forms.TextInput(attrs={'class': 'form-control'}),
      'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
    }

  def save(self, commit=True):
    instance = super().save(commit=False)
    instance.zone = Tigray_woreda.objects.get(woreda_name = self.cleaned_data.get('woreda')).zone
    if commit:
        instance.save()
    return instance

class Administrator_form(forms.ModelForm):
  class Meta:
    model = Administrator
    fields = ['civilian_role', 'analysis_role']