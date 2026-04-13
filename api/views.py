import json
import os
import urllib.error
import urllib.request
from urllib.parse import quote_plus

from django.contrib.auth import authenticate
from django.db.models import Q

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .filters import ArtifactFilter, BookingFilter, FlightFilter, HotelFilter
from .models import Booking, Flight, Hotel, RecentSearch, TravelArtifact, User
from .travel_dynamic import resolve_gemini_api_key, run_gemini_grounded_travel_agent


def _body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None


def _favorite_external_ids(user):
    return list(
        TravelArtifact.objects.filter(user=user, kind=TravelArtifact.KIND_FAVORITE).values_list(
            'external_id', flat=True
        )
    )


def _user_response(user):
    return {
        'id': str(user.id),
        'fullName': user.full_name or '',
        'email': user.email,
        'phoneNumber': user.phone_number or '',
        'avatarUrl': user.avatar_url or None,
        'nationality': user.nationality or '',
        'dateOfBirth': user.date_of_birth or '',
        'gender': user.gender or '',
        'passport': user.passport or '',
        'favoriteIds': _favorite_external_ids(user),
    }


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def _flight_out(f):
    return {
        'id': f.external_id,
        'airline': f.airline,
        'airlineLogo': f.airline_logo,
        'flightNumber': f.flight_number,
        'fromCity': f.from_city,
        'fromCode': f.from_code,
        'toCity': f.to_city,
        'toCode': f.to_code,
        'departureTime': f.departure_time,
        'arrivalTime': f.arrival_time,
        'date': f.date,
        'durationMinutes': f.duration_minutes,
        'stops': f.stops,
        'price': float(f.price),
        'currency': f.currency,
        'cabinClass': f.cabin_class,
        'seatsAvailable': f.seats_available,
        'baggage': float(f.baggage),
        'isFavorite': False,
    }


def _hotel_out(h):
    return {
        'id': h.external_id,
        'name': h.name,
        'location': h.location,
        'country': h.country,
        'imageUrl': h.image_url,
        'images': h.images or [],
        'rating': h.rating,
        'reviewCount': h.review_count,
        'pricePerNight': float(h.price_per_night),
        'currency': h.currency,
        'amenities': h.amenities or [],
        'description': h.description,
        'lat': h.lat,
        'lng': h.lng,
        'stars': h.stars,
        'isFavorite': False,
    }


def _booking_out(b):
    return {
        'id': str(b.id),
        'type': b.type,
        'title': b.title,
        'subtitle': b.subtitle,
        'imageUrl': b.image_url,
        'totalPrice': float(b.total_price),
        'currency': b.currency,
        'startDate': b.start_date,
        'endDate': b.end_date,
        'status': b.status,
        'reference': b.reference,
        'details': b.details or {},
    }


def _artifact_out(a):
    return {
        'id': a.id,
        'externalId': a.external_id,
        'kind': a.kind,
        'payload': a.payload,
        'userQuery': a.user_query,
        'aiSummary': a.ai_summary,
        'createdAt': a.created_at.isoformat(),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        full_name = (data.get('full_name') or data.get('fullName') or '').strip()
        phone = (data.get('phone_number') or data.get('phoneNumber') or '').strip()
        if not email or not password:
            return Response({'detail': 'email and password required'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email=email).exists():
            return Response({'detail': 'email already registered'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            full_name=full_name,
            phone_number=phone,
        )
        tok = _tokens_for(user)
        return Response({**tok, 'user': _user_response(user)}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        tok = _tokens_for(user)
        return Response({**tok, 'user': _user_response(user)})


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        refresh_raw = data.get('refresh')
        if not refresh_raw:
            return Response({'detail': 'refresh required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_raw)
            return Response({'access': str(token.access_token)})
        except TokenError:
            return Response({'detail': 'Invalid or expired token'}, status=status.HTTP_401_UNAUTHORIZED)


class MeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_response(request.user))

    def patch(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        if 'fullName' in data or 'full_name' in data:
            user.full_name = str(data.get('fullName') or data.get('full_name') or '')[:255]
        if 'phoneNumber' in data or 'phone_number' in data:
            user.phone_number = str(data.get('phoneNumber') or data.get('phone_number') or '')[:32]
        if 'nationality' in data:
            user.nationality = str(data.get('nationality') or '')[:128]
        if 'dateOfBirth' in data or 'date_of_birth' in data:
            user.date_of_birth = str(data.get('dateOfBirth') or data.get('date_of_birth') or '')[:32]
        if 'gender' in data:
            user.gender = str(data.get('gender') or '')[:32]
        if 'passport' in data:
            user.passport = str(data.get('passport') or '')[:64]
        if 'avatarUrl' in data or 'avatar_url' in data:
            user.avatar_url = str(data.get('avatarUrl') or data.get('avatar_url') or '')[:500]
        new_email = (data.get('email') or '').strip().lower()
        if new_email and new_email != user.email:
            if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                return Response({'detail': 'email already in use'}, status=status.HTTP_400_BAD_REQUEST)
            user.email = new_email
            user.username = new_email
        user.save()
        return Response(_user_response(user))


class ArtifactListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = TravelArtifact.objects.filter(user=request.user)
        flt = ArtifactFilter(request.GET, queryset=qs)
        return Response([_artifact_out(x) for x in flt.qs])

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        kind = data.get('kind')
        external_id = (data.get('external_id') or data.get('externalId') or '').strip()
        payload = data.get('payload')
        if kind not in (TravelArtifact.KIND_SAVED, TravelArtifact.KIND_FAVORITE):
            return Response({'detail': 'kind must be saved or favorite'}, status=status.HTTP_400_BAD_REQUEST)
        if not external_id:
            return Response({'detail': 'external_id required'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload, dict):
            return Response({'detail': 'payload must be object'}, status=status.HTTP_400_BAD_REQUEST)
        user_query = (data.get('user_query') or data.get('userQuery') or '')[:5000]
        ai_summary = (data.get('ai_summary') or data.get('aiSummary') or '')[:5000]
        obj, _ = TravelArtifact.objects.update_or_create(
            user=request.user,
            external_id=external_id,
            kind=kind,
            defaults={
                'payload': payload,
                'user_query': user_query,
                'ai_summary': ai_summary,
            },
        )
        return Response(_artifact_out(obj), status=status.HTTP_201_CREATED)


class ArtifactDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = TravelArtifact.objects.filter(pk=pk, user=request.user).delete()
        if not deleted:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtifactRemoveByExternalView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        external_id = (data.get('external_id') or data.get('externalId') or '').strip()
        kind = data.get('kind') or TravelArtifact.KIND_SAVED
        if not external_id:
            return Response({'detail': 'external_id required'}, status=status.HTTP_400_BAD_REQUEST)
        TravelArtifact.objects.filter(
            user=request.user, external_id=external_id, kind=kind
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FavoriteToggleView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        external_id = (data.get('external_id') or data.get('externalId') or '').strip()
        payload = data.get('payload') if isinstance(data.get('payload'), dict) else {}
        if not external_id:
            return Response({'detail': 'external_id required'}, status=status.HTTP_400_BAD_REQUEST)
        exists = TravelArtifact.objects.filter(
            user=request.user,
            external_id=external_id,
            kind=TravelArtifact.KIND_FAVORITE,
        ).first()
        if exists:
            exists.delete()
            return Response({'favorited': False, 'favoriteIds': _favorite_external_ids(request.user)})
        TravelArtifact.objects.create(
            user=request.user,
            external_id=external_id,
            kind=TravelArtifact.KIND_FAVORITE,
            payload=payload,
            user_query=(data.get('user_query') or data.get('userQuery') or '')[:5000],
            ai_summary=(data.get('ai_summary') or data.get('aiSummary') or '')[:5000],
        )
        return Response({'favorited': True, 'favoriteIds': _favorite_external_ids(request.user)})


class RecentSearchListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = RecentSearch.objects.filter(user=request.user)[:10]
        return Response([{'id': r.id, 'query': r.query, 'createdAt': r.created_at.isoformat()} for r in qs])

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        q = (data.get('query') or '').strip()[:500]
        if not q:
            return Response({'detail': 'query required'}, status=status.HTTP_400_BAD_REQUEST)
        RecentSearch.objects.create(user=request.user, query=q)
        ids = list(
            RecentSearch.objects.filter(user=request.user).order_by('-created_at').values_list('id', flat=True)[10:]
        )
        if ids:
            RecentSearch.objects.filter(pk__in=ids).delete()
        qs = RecentSearch.objects.filter(user=request.user)[:10]
        return Response([{'id': r.id, 'query': r.query} for r in qs], status=status.HTTP_201_CREATED)


class RecentSearchClearView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        RecentSearch.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _apply_text_q_hotels(qs, text):
    t = (text or '').strip()
    if not t:
        return qs
    return qs.filter(
        Q(name__icontains=t)
        | Q(location__icontains=t)
        | Q(country__icontains=t)
        | Q(description__icontains=t)
    )


def _apply_text_q_flights(qs, text):
    t = (text or '').strip()
    if not t:
        return qs
    return qs.filter(
        Q(from_city__icontains=t)
        | Q(to_city__icontains=t)
        | Q(airline__icontains=t)
        | Q(from_code__iexact=t)
        | Q(to_code__iexact=t)
    )


def _amenities_match(h_amenities, needed):
    if not needed:
        return True
    am = [str(x).lower() for x in (h_amenities or [])]
    for n in needed:
        nl = str(n).lower().strip()
        if not nl:
            continue
        if not any(nl == x or nl in x or x in nl for x in am):
            return False
    return True


def _sort_hotels(rows, sort_by):
    if sort_by == 'lowToHigh':
        rows.sort(key=lambda x: float(x.price_per_night))
    elif sort_by == 'highToLow':
        rows.sort(key=lambda x: -float(x.price_per_night))
    elif sort_by == 'topRated':
        rows.sort(key=lambda x: -float(x.rating))
    else:
        rows.sort(key=lambda x: -int(x.review_count))
    return rows


def _sort_flights(rows, sort_by):
    if sort_by == 'lowToHigh':
        rows.sort(key=lambda x: float(x.price))
    elif sort_by == 'highToLow':
        rows.sort(key=lambda x: -float(x.price))
    elif sort_by == 'topRated':
        rows.sort(key=lambda x: int(x.stops))
    else:
        rows.sort(key=lambda x: float(x.price))
    return rows


def _booking_hotel_search_url(name, location, country):
    ss = ' '.join(x for x in (name, location, country) if x).strip()
    return f'https://www.booking.com/searchresults.html?ss={quote_plus(ss)}&order=popularity'


def _booking_flight_url(from_code, to_code, date_str):
    fc = (from_code or '').strip().upper()
    tc = (to_code or '').strip().upper()
    d = (date_str or '').strip()[:10] or '2026-06-01'
    return (
        'https://www.booking.com/flights/index.en-gb.html?from='
        + quote_plus(f'{fc}.airport')
        + '&to='
        + quote_plus(f'{tc}.airport')
        + '&depart='
        + quote_plus(d)
    )


def _build_travel_agent_payload_static(data):
    query = (data.get('query') or '').strip()
    filter_kind = (data.get('filter') or 'all').strip().lower()
    sort_by = (data.get('sortBy') or 'popular').strip()
    search_type = (data.get('searchType') or 'both').strip().lower()
    min_rating = data.get('minRating')
    try:
        min_rating_f = float(min_rating) if min_rating is not None else 0.0
    except (TypeError, ValueError):
        min_rating_f = 0.0
    pr = data.get('priceRange') if isinstance(data.get('priceRange'), dict) else {}
    try:
        p_start = float(pr.get('start', 0))
    except (TypeError, ValueError):
        p_start = 0.0
    try:
        p_end = float(pr.get('end', 5000))
    except (TypeError, ValueError):
        p_end = 5000.0
    amenities = []
    raw_am = data.get('amenities')
    if isinstance(raw_am, list):
        amenities = [str(x) for x in raw_am]

    include_hotels = search_type in ('both', 'hotels', 'hotel', 'all', '')
    include_flights = search_type in ('both', 'flights', 'flight', 'all', '')

    if filter_kind == 'flight':
        include_hotels, include_flights = False, True
    elif filter_kind == 'hotel':
        include_hotels, include_flights = True, False
    elif filter_kind == 'package':
        include_hotels, include_flights = True, True

    def collect(text_filter: str):
        hotel_qs = _apply_text_q_hotels(Hotel.objects.all(), text_filter)
        flight_qs = _apply_text_q_flights(Flight.objects.all(), text_filter)

        hotel_qs = hotel_qs.filter(
            rating__gte=min_rating_f,
            price_per_night__gte=p_start,
            price_per_night__lte=p_end,
        )
        flight_qs = flight_qs.filter(price__gte=p_start, price__lte=p_end)

        h_rows = [h for h in hotel_qs if _amenities_match(h.amenities, amenities)]
        h_rows = _sort_hotels(h_rows, sort_by)

        f_rows = _sort_flights(list(flight_qs), sort_by)

        out_results = []
        minimal = []

        if include_hotels:
            for h in h_rows[:6]:
                offer = _booking_hotel_search_url(h.name, h.location, h.country)
                img = (h.image_url or '').strip()
                if not img and h.images:
                    img = str(h.images[0]) if h.images else ''
                rid = f'hotel_{h.external_id}'
                out_results.append(
                    {
                        'id': rid,
                        'type': 'hotel',
                        'title': h.name,
                        'subtitle': f'{h.location}, {h.country} • {h.stars}★',
                        'description': (h.description or '')[:260]
                        or f'Stays in {h.location} — open Booking.com to compare live rates.',
                        'price': float(h.price_per_night),
                        'currency': h.currency or 'USD',
                        'priceLabel': 'per night',
                        'rating': str(h.rating),
                        'badge': 'Booking.com',
                        'highlights': list(h.amenities or [])[:6],
                        'imageEmoji': '🏨',
                        'imageUrl': img,
                        'isBestPrice': h.review_count > 900,
                        'isRecommended': float(h.rating) >= 4.7,
                        'offerUrl': offer,
                        'details': {
                            'Location': h.location,
                            'Country': h.country,
                            'Stars': str(h.stars),
                            'Reviews': str(h.review_count),
                        },
                    }
                )
                minimal.append(
                    {'title': h.name, 'price': float(h.price_per_night), 'kind': 'hotel'}
                )

        if include_flights:
            for f in f_rows[:6]:
                offer = _booking_flight_url(f.from_code, f.to_code, f.date)
                logo = (f.airline_logo or '').strip()
                rid = f'flight_{f.external_id}'
                dur_h, dur_m = divmod(int(f.duration_minutes), 60)
                out_results.append(
                    {
                        'id': rid,
                        'type': 'flight',
                        'title': f'{f.from_code} → {f.to_code}',
                        'subtitle': f'{f.airline} • {f.cabin_class} • {f.stops} stop(s)',
                        'description': f'{f.from_city} to {f.to_city} on {f.date}.',
                        'price': float(f.price),
                        'currency': f.currency or 'USD',
                        'priceLabel': 'per person',
                        'badge': 'Booking.com',
                        'highlights': [
                            f.cabin_class,
                            f'{f.stops} stop(s)',
                            f'{dur_h}h {dur_m}m',
                        ],
                        'imageEmoji': '✈️',
                        'imageUrl': logo,
                        'isBestPrice': f.stops == 0,
                        'isRecommended': False,
                        'offerUrl': offer,
                        'details': {
                            'Airline': f.airline,
                            'From': f.from_code,
                            'To': f.to_code,
                            'Departure': f.departure_time,
                            'Arrival': f.arrival_time,
                            'Date': f.date,
                            'Duration': f'{dur_h}h {dur_m}m',
                            'Class': f.cabin_class,
                            'Stops': str(f.stops),
                        },
                    }
                )
                minimal.append(
                    {'title': f'{f.from_code}-{f.to_code}', 'price': float(f.price), 'kind': 'flight'}
                )

        return out_results, minimal

    out_results, minimal = collect(query)
    if not out_results and query:
        out_results, minimal = collect('')

    if not out_results:
        out_results, minimal = collect('')

    rtype = 'general'
    if include_hotels and not include_flights:
        rtype = 'hotel'
    elif include_flights and not include_hotels:
        rtype = 'flight'
    elif include_hotels and include_flights:
        rtype = 'package'

    return {
        'message': (
            f'Showing {len(out_results)} listing(s) from the local demo catalog '
            '(not live web). Set GEMINI_API_KEY in config/settings.py for real-time search.'
        ),
        'type': rtype,
        'results': out_results,
        'source': 'static_catalog',
    }


def _build_travel_agent_payload(data):
    """
    Default: Gemini + Google Search grounding (live web / Booking.com).
    Fallback: set TRAVEL_AGENT_STATIC_FALLBACK=1 to use seeded SQLite hotels/flights.
    """
    key = resolve_gemini_api_key()
    if key:
        try:
            return run_gemini_grounded_travel_agent(data)
        except Exception:
            if os.environ.get('TRAVEL_AGENT_STATIC_FALLBACK', '').strip() == '1':
                return _build_travel_agent_payload_static(data)
            raise
    if os.environ.get('TRAVEL_AGENT_STATIC_FALLBACK', '').strip() == '1':
        return _build_travel_agent_payload_static(data)
    raise ValueError(
        'GEMINI_API_KEY is not set. Paste your key in config/settings.py as GEMINI_API_KEY = "...", '
        'or set the GEMINI_API_KEY environment variable. Alternatively set TRAVEL_AGENT_STATIC_FALLBACK=1 '
        'to use demo catalog data only.'
    )


class TravelAgentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = _build_travel_agent_payload(data)
            return Response(payload)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            return Response(
                {'detail': 'travel agent failed', 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BookingListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Booking.objects.filter(user=request.user)
        flt = BookingFilter(request.GET, queryset=qs)
        return Response([_booking_out(x) for x in flt.qs])

    def post(self, request):
        data = _body(request)
        if data is None:
            return Response({'detail': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        required = ['type', 'title', 'totalPrice', 'startDate', 'endDate']
        for k in required:
            if k not in data:
                return Response({'detail': f'{k} required'}, status=status.HTTP_400_BAD_REQUEST)
        ref = (data.get('reference') or '').strip() or f"TRV{request.user.id}{Booking.objects.count()}"
        b = Booking.objects.create(
            user=request.user,
            type=str(data['type'])[:32],
            title=str(data['title'])[:255],
            subtitle=str(data.get('subtitle') or '')[:500],
            image_url=str(data.get('imageUrl') or data.get('image_url') or '')[:500],
            total_price=data['totalPrice'],
            currency=str(data.get('currency') or 'USD')[:8],
            start_date=str(data['startDate'])[:32],
            end_date=str(data['endDate'])[:32],
            status=str(data.get('status') or 'confirmed')[:32],
            reference=ref[:64],
            details=data.get('details') if isinstance(data.get('details'), dict) else {},
        )
        return Response(_booking_out(b), status=status.HTTP_201_CREATED)


class BookingCancelView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        updated = Booking.objects.filter(pk=pk, user=request.user).update(status='cancelled')
        if not updated:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        b = Booking.objects.get(pk=pk)
        return Response(_booking_out(b))


class FlightListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Flight.objects.all()
        flt = FlightFilter(request.GET, queryset=qs)
        fav_ids = set(_favorite_external_ids(request.user))
        out = []
        for f in flt.qs:
            d = _flight_out(f)
            d['isFavorite'] = f.external_id in fav_ids
            out.append(d)
        return Response(out)


class HotelListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Hotel.objects.all()
        flt = HotelFilter(request.GET, queryset=qs)
        fav_ids = set(_favorite_external_ids(request.user))
        out = []
        for h in flt.qs:
            d = _hotel_out(h)
            d['isFavorite'] = h.external_id in fav_ids
            out.append(d)
        return Response(out)
