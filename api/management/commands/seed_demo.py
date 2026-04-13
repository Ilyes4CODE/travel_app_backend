from django.core.management.base import BaseCommand

from api.models import Flight, Hotel


class Command(BaseCommand):
    help = 'Seed demo flights and hotels'

    def handle(self, *args, **options):
        flights = [
            {
                'external_id': '1',
                'airline': 'Emirates',
                'airline_logo': 'https://images.kiwi.com/airlines/64/EK.png',
                'flight_number': 'EK 201',
                'from_city': 'New York',
                'to_city': 'London',
                'from_code': 'JFK',
                'to_code': 'LHR',
                'departure_time': '08:30',
                'arrival_time': '14:45',
                'date': '2026-06-01',
                'duration_minutes': 435,
                'stops': 0,
                'price': 1250.00,
                'cabin_class': 'Economy',
            },
            {
                'external_id': '2',
                'airline': 'Air France',
                'airline_logo': 'https://images.kiwi.com/airlines/64/AF.png',
                'flight_number': 'AF 276',
                'from_city': 'Paris',
                'to_city': 'Tokyo',
                'from_code': 'CDG',
                'to_code': 'NRT',
                'departure_time': '22:15',
                'arrival_time': '11:30',
                'date': '2026-06-10',
                'duration_minutes': 735,
                'stops': 1,
                'price': 2100.00,
                'cabin_class': 'Business',
            },
            {
                'external_id': '3',
                'airline': 'Turkish Airlines',
                'airline_logo': 'https://images.kiwi.com/airlines/64/TK.png',
                'flight_number': 'TK 762',
                'from_city': 'Istanbul',
                'to_city': 'Dubai',
                'from_code': 'IST',
                'to_code': 'DXB',
                'departure_time': '14:20',
                'arrival_time': '18:45',
                'date': '2026-06-03',
                'duration_minutes': 265,
                'stops': 0,
                'price': 890.00,
                'cabin_class': 'Economy',
            },
            {
                'external_id': '4',
                'airline': 'Qatar Airways',
                'airline_logo': 'https://images.kiwi.com/airlines/64/QR.png',
                'flight_number': 'QR 942',
                'from_city': 'Doha',
                'to_city': 'Bangkok',
                'from_code': 'DOH',
                'to_code': 'BKK',
                'departure_time': '02:10',
                'arrival_time': '12:55',
                'date': '2026-07-12',
                'duration_minutes': 405,
                'stops': 0,
                'price': 780.00,
                'cabin_class': 'Economy',
            },
        ]
        for f in flights:
            Flight.objects.update_or_create(external_id=f['external_id'], defaults=f)

        hotels = [
            {
                'external_id': '1',
                'name': 'Grand Plaza Hotel',
                'location': 'Dubai',
                'country': 'UAE',
                'image_url': 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800',
                'images': [
                    'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800',
                    'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=800',
                ],
                'rating': 4.8,
                'review_count': 1280,
                'price_per_night': 250.0,
                'amenities': ['wifi', 'pool', 'gym', 'spa', 'restaurant', 'parking'],
                'description': 'Waterfront skyline views, rooftop pool, and quick metro access to Dubai Mall.',
                'stars': 5,
            },
            {
                'external_id': '2',
                'name': 'Marina Bay Resort',
                'location': 'Singapore',
                'country': 'Singapore',
                'image_url': 'https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=800',
                'images': ['https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=800'],
                'rating': 4.6,
                'review_count': 980,
                'price_per_night': 320.0,
                'amenities': ['wifi', 'pool', 'gym', 'restaurant'],
                'description': 'Marina Bay views, infinity pool, and family-friendly suites near Gardens by the Bay.',
                'stars': 5,
            },
            {
                'external_id': '3',
                'name': 'Alpine Lodge',
                'location': 'Zurich',
                'country': 'Switzerland',
                'image_url': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800',
                'images': ['https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800'],
                'rating': 4.9,
                'review_count': 740,
                'price_per_night': 180.0,
                'amenities': ['wifi', 'spa', 'restaurant', 'parking'],
                'description': 'Cozy alpine-style rooms near Old Town with spa and Swiss breakfast.',
                'stars': 4,
            },
            {
                'external_id': '4',
                'name': 'Seine Boutique Hotel',
                'location': 'Paris',
                'country': 'France',
                'image_url': 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=800',
                'images': ['https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=800'],
                'rating': 4.7,
                'review_count': 1120,
                'price_per_night': 210.0,
                'amenities': ['wifi', 'restaurant', 'gym'],
                'description': 'Boutique stay steps from the Seine with curated Paris guides at reception.',
                'stars': 4,
            },
        ]
        for h in hotels:
            Hotel.objects.update_or_create(external_id=h['external_id'], defaults=h)

        self.stdout.write(self.style.SUCCESS('Seeded flights and hotels'))
