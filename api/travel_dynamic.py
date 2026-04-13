"""
Live travel agent: Gemini + Google Search grounding.
Fetches current web results (Booking.com and other OTAs) — not the local SQLite catalog.

Requires GEMINI_API_KEY in Django settings (config.settings) or OS env. Grounding is billed per Google's pricing.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote_plus

# Models that support tools.google_search (see Google AI docs)
_GEMINI_MODELS = [
    'gemini-2.0-flash',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-3-flash-preview',
]


def resolve_gemini_api_key() -> str:
    """Prefer GEMINI_API_KEY in Django settings; fall back to OS environment."""
    try:
        from django.conf import settings

        raw = getattr(settings, 'GEMINI_API_KEY', '') or ''
        s = str(raw).strip()
        if s:
            return s
    except Exception:
        pass
    return (os.environ.get('GEMINI_API_KEY') or '').strip()


def _extract_first_json_object(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    t = re.sub(r'^```(?:json)?\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*```\s*$', '', t)
    start = t.find('{')
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(t)):
        ch = t[i]
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _grounding_uris(candidate: dict) -> tuple[list[str], list[str]]:
    """Return (all https uris, booking.com uris)."""
    meta = candidate.get('groundingMetadata') or {}
    chunks = meta.get('groundingChunks') or []
    all_u: list[str] = []
    book: list[str] = []
    for ch in chunks:
        web = ch.get('web') or {}
        uri = web.get('uri')
        if not uri or not isinstance(uri, str):
            continue
        u = uri.strip()
        if not u.startswith('http'):
            continue
        all_u.append(u)
        if 'booking.com' in u.lower():
            book.append(u)
    return all_u, book


def _pop_booking(book: list[str], gen: list[str]) -> str:
    if book:
        return book.pop(0)
    if gen:
        return gen.pop(0)
    return ''


def _normalize_results(
    raw_results: list,
    booking_uris: list[str],
    generic_uris: list[str],
) -> list[dict]:
    out: list[dict] = []
    book = list(booking_uris)
    gen = [u for u in generic_uris if u not in book]
    for i, item in enumerate(raw_results[:10]):
        if not isinstance(item, dict):
            continue
        r = dict(item)
        ou = str(r.get('offerUrl') or r.get('url') or r.get('bookingUrl') or '').strip()
        if not ou.startswith('https'):
            ou = _pop_booking(book, gen)
        elif 'booking.com' not in ou.lower() and book:
            # Prefer a Booking.com link from search when user expects Booking
            ou = book.pop(0)
        if not ou.startswith('https'):
            ss = quote_plus(
                f"{r.get('title', '')} {r.get('subtitle', '')}".strip() or 'hotels'
            )
            ou = f'https://www.booking.com/searchresults.html?ss={ss}&order=popularity'

        price = r.get('price')
        if price is not None and not isinstance(price, (int, float)):
            try:
                price = float(price)
            except (TypeError, ValueError):
                price = None
        if price is None:
            price = 0.0
            if not r.get('priceLabel'):
                r['priceLabel'] = 'See site'

        rid = str(r.get('id') or f'live_{i}')
        r['id'] = rid[:120]
        r['offerUrl'] = ou[:2000]
        r['price'] = float(price)
        r['currency'] = str(r.get('currency') or 'USD')[:8]
        r['type'] = str(r.get('type') or 'general').lower()[:20]
        r['title'] = str(r.get('title') or 'Offer')[:500]
        r['subtitle'] = str(r.get('subtitle') or '')[:500]
        r['description'] = str(r.get('description') or '')[:2000]
        r['imageEmoji'] = str(r.get('imageEmoji') or '🌐')[:8]
        img = r.get('imageUrl') or r.get('image_url')
        r['imageUrl'] = str(img).strip()[:2000] if img else ''
        if r['imageUrl'] and not r['imageUrl'].startswith('https://'):
            r['imageUrl'] = ''
        highlights = r.get('highlights')
        if isinstance(highlights, list):
            r['highlights'] = [str(x)[:200] for x in highlights[:12]]
        else:
            r['highlights'] = []
        details = r.get('details')
        r['details'] = details if isinstance(details, dict) else {}
        out.append(r)
    return out


def _build_prompt(data: dict) -> str:
    query = (data.get('query') or '').strip()
    filter_kind = (data.get('filter') or 'all').strip().lower()
    sort_by = (data.get('sortBy') or 'popular').strip()
    search_type = (data.get('searchType') or 'both').strip().lower()
    pr = data.get('priceRange') if isinstance(data.get('priceRange'), dict) else {}
    try:
        p_start = float(pr.get('start', 0))
    except (TypeError, ValueError):
        p_start = 0.0
    try:
        p_end = float(pr.get('end', 5000))
    except (TypeError, ValueError):
        p_end = 5000.0
    try:
        min_rating = float(data.get('minRating') or 0)
    except (TypeError, ValueError):
        min_rating = 0.0
    amenities = data.get('amenities') if isinstance(data.get('amenities'), list) else []
    am_s = ', '.join(str(x) for x in amenities[:12])

    return f"""You have Google Search. Use it now to find REAL, CURRENT travel options for this request.

USER REQUEST:
{query[:3500]}

APP FILTERS (respect when choosing what to return):
- filter tab: {filter_kind} (hotel / flight / package / all)
- search type preference: {search_type}
- sort preference: {sort_by}
- budget hint (per night for hotels, or ticket for flights): USD {p_start:.0f} – {p_end:.0f}
- minimum hotel guest rating (if hotels): {min_rating}
- required hotel amenities (if any): {am_s or 'none'}

SEARCH STRATEGY:
1. Run Google searches that include **site:booking.com** plus destination / dates / "hotel" or "flights" as appropriate.
2. You may also use other major booking sites if Booking has thin results, but **prioritize Booking.com** URLs in `offerUrl` when possible.
3. Pull **titles, locations, and prices ONLY from text that appears in the search snippets/pages you retrieve** — do not guess numbers.
4. If a price is not clearly shown in search content for an offer, set `"price": null` and `"priceLabel": "See site"`.
5. `offerUrl` must be a full **https** URL (property page, search results, or flight search on booking.com when possible).

OUTPUT FORMAT — return **ONLY** valid JSON (no markdown, no code fences):
{{
  "message": "One sentence: these offers come from live web search; prices may change on the site.",
  "type": "hotel" | "flight" | "package" | "general",
  "results": [
    {{
      "id": "unique_string",
      "type": "hotel" | "flight" | "package",
      "title": "plain text",
      "subtitle": "plain text",
      "description": "1–2 sentences from search context",
      "price": <number or null>,
      "currency": "USD",
      "priceLabel": "per night" | "per person" | "total" | "See site",
      "rating": "e.g. 4.6" or omit,
      "badge": "Booking.com" or null,
      "highlights": ["short", "chips"],
      "imageEmoji": "🏨" or "✈️",
      "imageUrl": "https://... only if you have a real image URL from search results, else omit or empty string",
      "isBestPrice": false,
      "isRecommended": false,
      "offerUrl": "https://www.booking.com/...",
      "details": {{}}
    }}
  ]
}}

Return **3 to 6** results when possible. If search returns nothing useful, return an empty results array and explain in message.
"""


def run_gemini_grounded_travel_agent(data: dict) -> dict:
    key = resolve_gemini_api_key()
    if not key:
        raise ValueError(
            'GEMINI_API_KEY is empty. Paste your key in config/settings.py (GEMINI_API_KEY = "...") '
            'or set the GEMINI_API_KEY environment variable.'
        )

    prompt = _build_prompt(data)
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'tools': [{'google_search': {}}],
        'generationConfig': {
            'temperature': 0.2,
            'maxOutputTokens': 8192,
        },
    }

    last_detail = ''
    for model in _GEMINI_MODELS:
        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{model}:generateContent?key={quote_plus(key)}'
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode()
                err_json = json.loads(err_body)
                last_detail = str(err_json.get('error', err_body))[:500]
            except Exception:
                last_detail = str(e)
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_detail = str(e)
            continue

        err = body.get('error')
        if err:
            last_detail = str(err.get('message', err))[:500]
            continue

        candidates = body.get('candidates') or []
        if not candidates:
            last_detail = 'No candidates from Gemini'
            continue

        cand = candidates[0]
        parts = (cand.get('content') or {}).get('parts') or []
        text = ''.join((p.get('text') or '') for p in parts if isinstance(p, dict))

        parsed = _extract_first_json_object(text)
        if not parsed:
            parsed = {
                'message': (text[:600] if text else 'Could not parse structured offers.'),
                'type': 'general',
                'results': [],
            }

        raw_results = parsed.get('results')
        if not isinstance(raw_results, list):
            raw_results = []

        all_u, book_u = _grounding_uris(cand)
        results = _normalize_results(raw_results, book_u, all_u)

        return {
            'message': str(parsed.get('message') or '')[:2000],
            'type': str(parsed.get('type') or 'general')[:32],
            'results': results,
            'source': 'gemini_google_search',
            'model': model,
        }

    raise RuntimeError(
        f'Gemini grounded search failed for all models. Last detail: {last_detail}'
    )
