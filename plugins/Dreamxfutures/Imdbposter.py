import re
import aiohttp
import warnings
import logging
from io import BytesIO
from PIL import Image
from info import DREAMXBOTZ_IMAGE_FETCH, TMDB_API_KEY
from imdb import Cinemagoer

logger = logging.getLogger(__name__)
ia = Cinemagoer()
LONG_IMDB_DESCRIPTION = False

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
        logger.info("Image fetching is disabled.")
        return url

    try:
        session = await get_session()
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"Failed to fetch image: {response.status} for {url}")
                return None

            data = await response.read()
            img = Image.open(BytesIO(data))
            img = img.resize(size, Image.LANCZOS)

            out = BytesIO()
            img.save(out, format="JPEG")
            out.seek(0)
            return out

    except aiohttp.ClientError as e:
        logger.error(f"HTTP request error in fetch_image: {e}")
    except IOError as e:
        logger.error(f"I/O error in fetch_image: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in fetch_image: {e}")

    return None

async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()

def list_to_str(lst):
    if lst:
        return ", ".join(map(str, lst))
    return ""

async def get_movie_details(query, id=False, file=None):
    try:
        if not id:
            query = query.strip().lower()
            title = query
            year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
                title = query.replace(year, "").strip()
            elif file is not None:
                year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
                if year:
                    year = list_to_str(year[:1])
            else:
                year = None
            movieid = ia.search_movie(title.lower(), results=10)
            if not movieid:
                return None
            if year:
                filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
                if not filtered:
                    filtered = movieid
            else:
                filtered = movieid
            
            filtered_kind = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
            if not filtered_kind:
                logger.info("No matches found for kind 'movie' or 'tv series', falling back to filtered list.")
                movieid = filtered
            else:
                movieid = filtered_kind
            
            movieid = movieid[0].movieID
        else:
            movieid = query
        movie = ia.get_movie(movieid)
        ia.update(movie, info=['main', 'vote details'])
        
        if movie.get("original air date"):
            date = movie["original air date"]
        elif movie.get("year"):
            date = movie.get("year")
        else:
            date = "N/A"
            
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
        else:
            plot = movie.get('plot outline')
        if plot and len(plot) > 800:
            plot = plot[:800] + "..."
            
        poster_url = movie.get('full-size cover url')
        return {
            'title': movie.get('title'),
            'votes': movie.get('votes'),
            "aka": list_to_str(movie.get("akas")),
            "seasons": movie.get("number of seasons"),
            "box_office": movie.get('box office'),
            'localized_title': movie.get('localized title'),
            'kind': movie.get("kind"),
            "imdb_id": f"tt{movie.get('imdbID')}",
            "cast": list_to_str(movie.get("cast")),
            "runtime": list_to_str(movie.get("runtimes")),
            "countries": list_to_str(movie.get("countries")),
            "certificates": list_to_str(movie.get("certificates")),
            "languages": list_to_str(movie.get("languages")),
            "director": list_to_str(movie.get("director")),
            "writer": list_to_str(movie.get("writer")),
            "producer": list_to_str(movie.get("producer")),
            "composer": list_to_str(movie.get("composer")),
            "cinematographer": list_to_str(movie.get("cinematographer")),
            "music_team": list_to_str(movie.get("music department")),
            "distributors": list_to_str(movie.get("distributors")),
            'release_date': date,
            'year': movie.get('year'),
            'genres': list_to_str(movie.get("genres")),
            'poster_url': poster_url + "._V1_SX1440.jpg" if poster_url.endswith("@.jpg") else poster_url,
            'plot': plot,
            'rating': str(movie.get("rating", "N/A")),
            'url': f'https://www.imdb.com/title/tt{movieid}'
        }
    except Exception as e:
        logger.exception(f"An error occurred in get_movie_details: {e}")
        return None

async def get_movie_detailsx(query, id=False, file=None):
    q = str(query).strip()
    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Official TMDB Search API
            search_url = "https://api.themoviedb.org/3/search/movie"
            params = {"api_key": TMDB_API_KEY, "query": q}
            async with session.get(search_url, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"TMDB Search API failed [{resp.status}] for query={q}")
                    return None
                search_data = await resp.json()
                results = search_data.get('results')
                if not results:
                    logger.error(f"No results found on TMDB for query={q}")
                    return None
                tmdb_id = results[0]['id']

            # Step 2: Official TMDB Movie Details API
            details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            detail_params = {"api_key": TMDB_API_KEY, "append_to_response": "credits"}
            async with session.get(details_url, params=detail_params) as resp:
                if resp.status != 200:
                    logger.error(f"TMDB Details API failed [{resp.status}] for id={tmdb_id}")
                    return None
                data = await resp.json()

        # Structuring data precisely for your bot template
        details = {}
        details['title'] = data.get('title')
        release_date = data.get('release_date')
        details['release_date'] = release_date
        details['year'] = int(release_date.split('-')[0]) if release_date else None
        details['rating'] = round(float(data.get('vote_average', 0)), 1) if data.get('vote_average') is not None else None
        details['votes'] = int(data.get('vote_count', 0))
        details['runtime'] = f"{data.get('runtime', 0)} min" if data.get('runtime') else "N/A"
        details['certificates'] = "N/A"
        details['tmdb_url'] = f"https://www.themoviedb.org/movie/{tmdb_id}"
        
        details['genres'] = [g.get('name', '').strip() for g in data.get('genres', [])] if data.get('genres') else []
        details['languages'] = [l.get('english_name', '').strip() for l in data.get('spoken_languages', [])] if data.get('spoken_languages') else []
        details['countries'] = [c.get('name', '').strip() for c in data.get('production_countries', [])] if data.get('production_countries') else []
        
        credits = data.get('credits', {})
        details['director'] = [crew.get('name', '').strip() for crew in credits.get('crew', []) if crew.get('job') == 'Director']
        details['writer'] = [crew.get('name', '').strip() for crew in credits.get('crew', []) if crew.get('job') in ['Writer', 'Screenplay']]
        details['producer'] = [crew.get('name', '').strip() for crew in credits.get('crew', []) if crew.get('job') == 'Producer']
        details['composer'] = [crew.get('name', '').strip() for crew in credits.get('crew', []) if crew.get('job') == 'Original Music Composer']
        details['cinematographer'] = [crew.get('name', '').strip() for crew in credits.get('crew', []) if crew.get('job') == 'Cinematographer']
        details['cast'] = [cast.get('name', '').strip() for cast in credits.get('cast', [])[:10]]
        
        details['plot'] = data.get('overview', 'N/A')
        details['tagline'] = data.get('tagline', '')
        details['box_office'] = f"${data.get('revenue', 0):,}" if data.get('revenue') else None
        details['distributors'] = []
        details['imdb_id'] = data.get('imdb_id')
        details['tmdb_id'] = tmdb_id
        
        poster_path = data.get('poster_path')
        details['poster_url'] = f"https://image.tmdb.org/t/p/w1280{poster_path}" if poster_path else None

        backdrop_path = data.get('backdrop_path')
        details['backdrop_url'] = f"https://image.tmdb.org/t/p/w1280{backdrop_path}" if backdrop_path else None

        return details
    except Exception as e:
        logger.error(f"An error occurred in get_movie_detailsx: {e}")
        return None
