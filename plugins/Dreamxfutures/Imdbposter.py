import re
import aiohttp
import warnings
import logging
from io import BytesIO
from PIL import Image
from info import DREAMXBOTZ_IMAGE_FETCH, TMDB_API_KEY

logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = None
warnings.simplefilter("ignore", Image.DecompressionBombWarning)

_session: aiohttp.ClientSession | None = None

async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session

async def fetch_image(url, size=(860, 1200)):
    if not DREAMXBOTZ_IMAGE_FETCH:
        return url

    try:
        session = await get_session()
        async with session.get(url) as response:
            if response.status != 200:
                return None

            data = await response.read()
            img = Image.open(BytesIO(data))
            img = img.resize(size, Image.LANCZOS)

            out = BytesIO()
            img.save(out, format="JPEG")
            out.seek(0)
            return out

    except Exception as e:
        logger.error(f"Image fetch error: {e}")
        return None

async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()

def list_to_str(lst):
    if lst:
        return ", ".join(map(str, lst))
    return "N/A"

# Ab get_movie_details bhi TMDB hi use karega!
async def get_movie_details(query, id=False, file=None):
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY missing hai!")
        return None
        
    q = str(query).strip()
    year = None
    
    # Saal (Year) nikalne ka logic taaki TMDB exact search kare
    year_match = re.findall(r'[1-2]\d{3}$', q, re.IGNORECASE)
    if year_match:
        year = year_match[0]
        q = q.replace(year, "").strip()
    elif file is not None:
        year_match = re.findall(r'[1-2]\d{3}', str(file), re.IGNORECASE)
        if year_match:
            year = year_match[0]

    try:
        async with aiohttp.ClientSession() as session:
            # Multi-search API
            search_url = "https://api.themoviedb.org/3/search/multi"
            params = {"api_key": TMDB_API_KEY, "query": q}
            if year:
                params["primary_release_year"] = year
                
            async with session.get(search_url, params=params) as resp:
                if resp.status != 200:
                    return None
                search_data = await resp.json()
                results = search_data.get('results')
                if not results:
                    return None
                
                item = results[0]
                tmdb_id = item.get('id')
                media_type = item.get('media_type', 'movie')

            # Fetch precise details
            if media_type == 'tv':
                details_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}"
            else:
                details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
                
            detail_params = {"api_key": TMDB_API_KEY, "append_to_response": "credits"}
            async with session.get(details_url, params=detail_params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

        # Data structure formatting (bot template ke liye)
        details = {}
        details['title'] = data.get('title') or data.get('name', 'N/A')
        
        release_date = data.get('release_date') or data.get('first_air_date')
        details['release_date'] = release_date if release_date else "N/A"
        details['year'] = release_date.split('-')[0] if release_date else "N/A"
        
        details['rating'] = str(round(float(data.get('vote_average', 0)), 1)) if data.get('vote_average') else "N/A"
        details['votes'] = data.get('vote_count', 0)
        
        runtime = data.get('runtime')
        if not runtime and data.get('episode_run_time'):
            runtime = data.get('episode_run_time')[0]
        details['runtime'] = f"{runtime} min" if runtime else "N/A"
        
        details['url'] = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"
        details['tmdb_url'] = details['url']
        details['imdb_id'] = data.get('imdb_id', 'N/A')
        
        genres = [g.get('name', '') for g in data.get('genres', [])]
        details['genres'] = ", ".join(genres) if genres else "N/A"
        
        languages = [l.get('english_name', '') for l in data.get('spoken_languages', [])]
        details['languages'] = ", ".join(languages) if languages else "N/A"
        
        countries = [c.get('name', '') for c in data.get('production_countries', [])]
        details['countries'] = ", ".join(countries) if countries else "N/A"
        
        credits = data.get('credits', {})
        crew = credits.get('crew', [])
        
        director = [c.get('name') for c in crew if c.get('job') == 'Director']
        details['director'] = ", ".join(director) if director else "N/A"
        
        cast = [c.get('name') for c in credits.get('cast', [])[:10]]
        details['cast'] = ", ".join(cast) if cast else "N/A"
        
        plot = data.get('overview', 'N/A')
        if plot and len(plot) > 800:
            plot = plot[:800] + "..."
        details['plot'] = plot
        
        poster_path = data.get('poster_path')
        details['poster_url'] = f"https://image.tmdb.org/t/p/w1280{poster_path}" if poster_path else None
        
        details['aka'] = "N/A"
        details['seasons'] = data.get('number_of_seasons', "N/A")
        details['box_office'] = f"${data.get('revenue', 0):,}" if data.get('revenue') else "N/A"
        details['localized_title'] = details['title']
        details['kind'] = media_type
        details['certificates'] = "N/A"
        details['writer'] = "N/A"
        details['producer'] = "N/A"
        details['composer'] = "N/A"
        details['cinematographer'] = "N/A"
        details['music_team'] = "N/A"
        details['distributors'] = "N/A"

        return details
    except Exception as e:
        logger.error(f"Error in get_movie_details: {e}")
        return None

# Backup function
async def get_movie_detailsx(query, id=False, file=None):
    return await get_movie_details(query, id, file)

