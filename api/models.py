from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True, default='')
    phone_number = models.CharField(max_length=32, blank=True, default='')
    nationality = models.CharField(max_length=128, blank=True, default='')
    date_of_birth = models.CharField(max_length=32, blank=True, default='')
    gender = models.CharField(max_length=32, blank=True, default='')
    passport = models.CharField(max_length=64, blank=True, default='')
    avatar_url = models.CharField(max_length=500, blank=True, default='')
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)


class TravelArtifact(models.Model):
    KIND_SAVED = 'saved'
    KIND_FAVORITE = 'favorite'
    KIND_CHOICES = [
        (KIND_SAVED, 'saved'),
        (KIND_FAVORITE, 'favorite'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='artifacts',
    )
    external_id = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    payload = models.JSONField(default=dict)
    user_query = models.TextField(blank=True, default='')
    ai_summary = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'external_id', 'kind'],
                name='uniq_user_external_kind',
            )
        ]


class RecentSearch(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recent_searches',
    )
    query = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Booking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    type = models.CharField(max_length=32)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=500, blank=True, default='')
    image_url = models.CharField(max_length=500, blank=True, default='')
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='USD')
    start_date = models.CharField(max_length=32)
    end_date = models.CharField(max_length=32)
    status = models.CharField(max_length=32, default='confirmed')
    reference = models.CharField(max_length=64)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Flight(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    airline = models.CharField(max_length=128)
    airline_logo = models.CharField(max_length=500, blank=True, default='')
    flight_number = models.CharField(max_length=32)
    from_city = models.CharField(max_length=128)
    from_code = models.CharField(max_length=8)
    to_city = models.CharField(max_length=128)
    to_code = models.CharField(max_length=8)
    departure_time = models.CharField(max_length=16)
    arrival_time = models.CharField(max_length=16)
    date = models.CharField(max_length=32)
    duration_minutes = models.PositiveIntegerField()
    stops = models.PositiveSmallIntegerField(default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='USD')
    cabin_class = models.CharField(max_length=32, default='Economy')
    seats_available = models.PositiveIntegerField(default=10)
    baggage = models.DecimalField(max_digits=6, decimal_places=1, default=23)


class Hotel(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    country = models.CharField(max_length=128)
    image_url = models.CharField(max_length=500, blank=True, default='')
    images = models.JSONField(default=list)
    rating = models.FloatField()
    review_count = models.PositiveIntegerField()
    price_per_night = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='USD')
    amenities = models.JSONField(default=list)
    description = models.TextField(blank=True, default='')
    lat = models.FloatField(default=0)
    lng = models.FloatField(default=0)
    stars = models.PositiveSmallIntegerField(default=4)
