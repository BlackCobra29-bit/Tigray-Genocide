from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid

class Tigray_woreda(models.Model):
    woreda_name = models.CharField(primary_key=True, max_length = 255)
    latitude = models.CharField(max_length=255)
    longitude = models.CharField(max_length=255)
    zone = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["woreda_name"]
        verbose_name_plural = 'Tigray Geolocations'

    def __str__(self):
        return f'{self.woreda_name}'

class Civilian_victims(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # sender options
    sender_fullname = models.CharField(max_length=255, null=True, blank=True)
    sender_location = models.CharField(max_length=255, null=True, blank=True)
    sender_email = models.EmailField(null=True, blank=True)
    sender_phone = models.CharField(max_length=255, null=True, blank=True)
    # end of sender options
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.DO_NOTHING)
    full_name = models.CharField(max_length=255)
    Gender_Choices = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Unknown', 'Unknown')
    ]
    gender = models.CharField(max_length=255, choices=Gender_Choices)
    place_of_killing = models.CharField(max_length=255, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    woreda = models.ForeignKey(Tigray_woreda, null=True, on_delete=models.DO_NOTHING)
    zone = models.CharField(max_length=255)
    source = models.CharField(max_length=255, null=True, blank=True)
    source_link = models.TextField(null=True, blank=False)
    Perpetrator_Choices = [
        ('Died from lack of food', 'Died from lack of food'),
        ('Died from lack of medicine', 'Died from lack of medicine'),
        ('Killed by Ethiopian forces', 'Killed by Ethiopian forces'),
        ('Killed by Eritrean forces', 'Killed by Eritrean forces'),
        ('Killed by Ethiopian and Eritrean forces', 'Killed by Ethiopian and Eritrean forces'),
        ('Killed by Amhara militia and Fano', 'Killed by Amhara militia and Fano')
    ]
    perpetrator = models.CharField(max_length=255, choices=Perpetrator_Choices)
    date_of_event = models.DateField(null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    picture = models.ImageField(default = 'civilian_victims_pic/default.png', upload_to = 'civilian_victims_pic', blank = True)
    approval = models.BooleanField(default=False)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name = "Verified Civilian Victim"
        verbose_name_plural = "Verified Civilian Victims"
        indexes = [
            models.Index(fields=["approval", "date_created"]),
            models.Index(fields=["approval", "woreda"]),
            models.Index(fields=["approval", "zone"]),
            models.Index(fields=["approval", "perpetrator"]),
            models.Index(fields=["approval", "gender"]),
            models.Index(
                fields=["full_name", "woreda"],
                name="civilian_name_woreda_idx",
            ),
        ]

    def __str__(self):
        return f'{self.full_name}'

class Analysis_articles(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Automatically generated unique ID for this article."
    )

    author = models.ForeignKey(
        User,
        null=True,
        on_delete=models.DO_NOTHING,
        help_text="Select the author who created this article."
    )

    title = models.TextField(
        help_text="Enter a clear and descriptive title for the article."
    )

    thumbnail = models.ImageField(
        upload_to='articles_thumbnail',
        help_text="Upload a thumbnail image for this article."
    )

    content = models.TextField(
        help_text="Write the main content of the article here."
    )

    endf_related = models.BooleanField(
        default=False,
        help_text="Check this if the article is related to ENDF."
    )

    personal_account = models.BooleanField(
        default=False,
        help_text="Mark this if the article is from a personal account or experience."
    )

    approval = models.BooleanField(
        default=False,
        help_text="Indicates whether the article has been approved for publication."
    )

    draft = models.BooleanField(
        default=False,
        help_text="Mark this if the article is still a draft and not yet ready to publish."
    )

    date_created = models.DateTimeField(
        default=timezone.now,
        help_text="This shows when the article was created."
    )

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = "Analysis articles"
        indexes = [
            models.Index(fields=["approval", "draft", "date_created"]),
            models.Index(fields=["approval", "draft", "endf_related"]),
            models.Index(fields=["approval", "draft", "personal_account"]),
        ]

    def __str__(self):
        return f'{self.title}'


class Article_comments(models.Model):
    article = models.ForeignKey(Analysis_articles, on_delete=models.CASCADE)
    name = models.TextField(max_length=255)
    email = models.CharField(max_length=255)
    content = models.TextField()
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = 'Article comments'

    def __str__(self):
        return f'{self.article} comment'

class Webinar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    webinar_title = models.TextField()
    webinar_content = models.TextField()
    webinar_video_url = models.CharField(max_length=255, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = 'Webinar Discussions'
        indexes = [
            models.Index(
                fields=["date_created"],
                name="webinar_created_idx",
            ),
        ]

    def __str__(self):
        return f'{self.webinar_title} comment'

class Photo_archive(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    location = models.CharField(max_length=255)
    woreda = models.ForeignKey(Tigray_woreda, null=True, on_delete=models.DO_NOTHING)
    date_of_event = models.DateField(null=True, blank=True)
    description = models.TextField()
    photo = models.ImageField(upload_to = 'photo_archive')
    graphic = models.BooleanField(default=False)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = 'Photo archives'
        indexes = [
            models.Index(fields=["woreda", "date_created"]),
        ]

    def __str__(self):
        return f'{self.description}'

class Video_archive(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    location = models.CharField(max_length=255)
    woreda = models.ForeignKey(Tigray_woreda, null=True, on_delete=models.DO_NOTHING)
    date_of_event = models.DateField(max_length=255, null=True, blank=True)
    description = models.TextField()
    online_link = models.CharField(max_length=255)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = 'Video archives'
        indexes = [
            models.Index(fields=["woreda", "date_created"]),
        ]

    def __str__(self):
        return f'{self.description}'

class Administrator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    civilian_role = models.BooleanField(default=False)
    analysis_role = models.BooleanField(default=False)
    admin_photo = models.ImageField(upload_to = 'admin_pic', default = 'admin_pic/default.png')
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = 'Adminstrator'

    def __str__(self):
        return f'{self.user.username}'

class Hero_images(models.Model):
    hero_image = models.ImageField(upload_to = 'hero-images')
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = 'Hero images'

    def __str__(self):
        return f'{self.hero_image}'
        
class Webmail_password_manager(models.Model):
    password = models.CharField(max_length = 255)
    date_created = models.DateTimeField(default=timezone.now)
        
class Unverified_civilian(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.CharField(max_length=255)
    number_of_civilian = models.IntegerField()
    Perpetrator_Choices = [
        ('Died from lack of food', 'Died from lack of food'),
        ('Died from lack of medicine', 'Died from lack of medicine'),
        ('Killed by Ethiopian forces', 'Killed by Ethiopian forces'),
        ('Killed by Eritrean forces', 'Killed by Eritrean forces'),
        ('Killed by Ethiopian and Eritrean forces', 'Killed by Ethiopian and Eritrean forces'),
        ('Killed by Amhara militia and Fano', 'Killed by Amhara militia and Fano')
    ]
    perpetrator = models.CharField(max_length=255, choices=Perpetrator_Choices)
    woreda = models.ForeignKey(Tigray_woreda, null=True, on_delete=models.DO_NOTHING)
    zone = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    source_link = models.TextField(null=True, blank=False)
    remark = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_created"]
        verbose_name_plural = 'Unverified Civilian victims'
        indexes = [
            models.Index(fields=["woreda", "date_created"]),
            models.Index(fields=["zone", "date_created"]),
            models.Index(fields=["perpetrator", "date_created"]),
        ]

    def __str__(self):
        return f'{self.location}'
