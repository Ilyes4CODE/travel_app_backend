import django_filters
from django.db.models import Q

from .models import Booking, Flight, Hotel, TravelArtifact


class FlightFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_q')

    def filter_q(self, queryset, name, value):
        t = (value or '').strip()
        if not t:
            return queryset
        return queryset.filter(
            Q(from_city__icontains=t)
            | Q(to_city__icontains=t)
            | Q(airline__icontains=t)
            | Q(from_code__iexact=t)
            | Q(to_code__iexact=t)
        )

    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    from_code = django_filters.CharFilter(field_name='from_code', lookup_expr='iexact')
    to_code = django_filters.CharFilter(field_name='to_code', lookup_expr='iexact')
    cabin_class = django_filters.CharFilter(field_name='cabin_class', lookup_expr='iexact')
    stops = django_filters.NumberFilter(field_name='stops', lookup_expr='exact')

    class Meta:
        model = Flight
        fields = [
            'min_price',
            'max_price',
            'from_code',
            'to_code',
            'cabin_class',
            'stops',
            'airline',
        ]


class HotelFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_q')

    def filter_q(self, queryset, name, value):
        t = (value or '').strip()
        if not t:
            return queryset
        return queryset.filter(
            Q(name__icontains=t)
            | Q(location__icontains=t)
            | Q(country__icontains=t)
            | Q(description__icontains=t)
        )

    min_price = django_filters.NumberFilter(field_name='price_per_night', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price_per_night', lookup_expr='lte')
    min_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='gte')
    country = django_filters.CharFilter(field_name='country', lookup_expr='icontains')
    city = django_filters.CharFilter(field_name='location', lookup_expr='icontains')
    stars = django_filters.NumberFilter(field_name='stars', lookup_expr='exact')

    class Meta:
        model = Hotel
        fields = ['min_price', 'max_price', 'min_rating', 'country', 'city', 'stars']


class BookingFilter(django_filters.FilterSet):
    class Meta:
        model = Booking
        fields = ['status', 'type']


class ArtifactFilter(django_filters.FilterSet):
    class Meta:
        model = TravelArtifact
        fields = ['kind']
