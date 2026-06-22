from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .. import config
from ..services import radarr, sonarr, tmdb

MOVIES_PER_PAGE = 8


def _admin_only(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else 0
    return user_id in config.TELEGRAM_ALLOWED_IDS


def _shorten(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3].rstrip() + "..."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "CineBot — tu servidor de pelis en casa.\n\n"
        "/search <película> — buscar película\n"
        "/tv <serie> — buscar serie\n"
        "/person <nombre> — buscar actor/director\n"
        "/status — cola de descargas\n"
        "/help — ayuda"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Comandos*\n"
        "/search \\<película\\> — buscar película en TMDB\n"
        "/tv \\<serie\\> — buscar serie en TMDB\n"
        "/person \\<nombre\\> — buscar actor o director\n"
        "/status — ver cola de descargas\n\n"
        "*Flujo típico:*\n"
        "1\\. `/search inception`\n"
        "2\\. Tocás un resultado\n"
        "3\\. Tocás *Agregar a Radarr*",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def search_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /search <nombre de película>")
        return

    query = " ".join(context.args)
    try:
        results = tmdb.search_movies(query)
    except Exception as e:
        await update.message.reply_text(f"Error buscando: {e}")
        return

    if not results:
        await update.message.reply_text(f"No encontré resultados para \"{query}\"")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{'⭐' if m.rating >= 7 else '🎬'} {m.title} ({m.year})",
            callback_data=f"movie:{m.tmdb_id}"
        )]
        for m in results
    ]
    await update.message.reply_text(
        f"Resultados para *{query}*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def search_tv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /tv <nombre de serie>")
        return

    query = " ".join(context.args)
    try:
        results = tmdb.search_tv(query)
    except Exception as e:
        await update.message.reply_text(f"Error buscando: {e}")
        return

    if not results:
        await update.message.reply_text(f"No encontré resultados para \"{query}\"")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"📺 {s.name} ({s.year})",
            callback_data=f"tv:{s.tmdb_id}"
        )]
        for s in results
    ]
    await update.message.reply_text(
        f"Resultados para *{query}*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def search_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /person <nombre del actor/director>")
        return

    query = " ".join(context.args)
    try:
        results = tmdb.search_person(query)
    except Exception as e:
        await update.message.reply_text(f"Error buscando: {e}")
        return

    if not results:
        await update.message.reply_text(f"No encontré a \"{query}\"")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"👤 {p.name} — {p.known_for}",
            callback_data=f"person_bio:{p.tmdb_id}"
        )]
        for p in results
    ]
    await update.message.reply_text(
        f"Resultados para *{query}*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        q = radarr.get_queue()
        sq = sonarr.get_queue()
        h = radarr.get_history()
        sh = sonarr.get_history()
        movies = radarr.get_all_movies()

        lines = []

        if q:
            lines.append("📥 Bajando")
            for item in q[:3]:
                mid = item.get("movieId")
                title = movies.get(mid, item.get("title", "?"))
                if len(title) > 35:
                    title = title[:32] + "..."
                size = item.get("size", 1) or 1
                left = item.get("sizeleft", 0) or 0
                pct = int((1 - left / size) * 100)
                lines.append(f"🎬 {title} {pct}%")

        if sq:
            if not q:
                lines.append("📥 Bajando")
            for item in sq[:3]:
                series = item.get("series", {}).get("title", item.get("title", "?"))
                if len(series) > 35:
                    series = series[:32] + "..."
                size = item.get("size", 1) or 1
                left = item.get("sizeleft", 0) or 0
                pct = int((1 - left / size) * 100)
                lines.append(f"📺 {series} {pct}%")

        if h:
            shown = [r for r in h[:15] if r.get("eventType") in ("downloadFolderImported", "downloadFailed")]
            if shown:
                lines.append("\n📽 Películas")
                for item in shown[:5]:
                    evt = item.get("eventType", "?")
                    mid = item.get("movieId")
                    title = movies.get(mid)
                    if not title:
                        title = item.get("sourceTitle", "?")
                        if len(title) > 35:
                            title = title[:32] + "..."
                    icon = "✅" if "mport" in evt else "❌"
                    lines.append(f"{icon} {title}")

        if sh:
            shown = [r for r in sh[:15] if r.get("eventType") in ("downloadFolderImported", "downloadFailed")]
            if shown:
                lines.append("\n📺 Series")
                for item in shown[:5]:
                    evt = item.get("eventType", "?")
                    series = item.get("series", {})
                    ep = item.get("episode", {})
                    sn = ep.get("seasonNumber", 0)
                    en = ep.get("episodeNumber", 0)
                    name = series.get("title")
                    if not name:
                        src = item.get("sourceTitle", "")
                        parts = src.replace("/data/media/tv/", "").split("/")
                        name = parts[0] if parts else "?"
                        if len(parts) > 1:
                            try:
                                sn = int(parts[1].replace("Season ", ""))
                            except Exception:
                                pass
                    show = f"{name} S{sn:02d}" if sn else str(name)[:35]
                    if en:
                        show += f"E{en:02d}"
                    if len(show) > 35:
                        show = show[:32] + "..."
                    icon = "✅" if "mport" in evt else "❌"
                    lines.append(f"{icon} {show}")

        if not lines:
            lines.append("Nada en cola ni historial.")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not _admin_only(update):
        await query.edit_message_text("No autorizado.")
        return

    data = query.data

    if data.startswith("movie:"):
        tid = int(data.split(":")[1])
        await _show_movie_details(query, tid)

    elif data.startswith("add_movie:"):
        tid = int(data.split(":")[1])
        await _add_movie(query, tid)

    elif data.startswith("tv:"):
        tid = int(data.split(":")[1])
        await _show_tv_details(query, tid)

    elif data.startswith("add_tv:"):
        tid = int(data.split(":")[1])
        await _add_tv(query, tid)

    elif data.startswith("cast_tv:"):
        tid = int(data.split(":")[1])
        await _show_tv_cast(query, tid)

    elif data.startswith("seasons:"):
        tid = int(data.split(":")[1])
        await _show_tv_seasons(query, tid)

    elif data.startswith("add_tv_season:"):
        parts = data.split(":")
        tid = int(parts[1])
        sn = int(parts[2])
        await _add_tv_season(query, tid, sn)

    elif data.startswith("cast:"):
        tid = int(data.split(":")[1])
        await _show_cast(query, tid)

    elif data.startswith("person_bio:"):
        pid = int(data.split(":")[1])
        await _show_person_bio(query, pid)

    elif data.startswith("person_movies:"):
        pid = int(data.split(":")[1])
        await _show_person_movies(query, pid, page=1)

    elif data.startswith("person_movies_p"):
        parts = data.split(":")
        pid = int(parts[1])
        page = int(parts[2])
        await _show_person_movies(query, pid, page=page)

    elif data.startswith("person_tv:"):
        pid = int(data.split(":")[1])
        await _show_person_tv(query, pid, page=1)

    elif data.startswith("person_tv_p:"):
        parts = data.split(":")
        pid = int(parts[1])
        page = int(parts[2])
        await _show_person_tv(query, pid, page=page)

    elif data.startswith("t_from_person:"):
        tid = int(data.split(":")[1])
        await _show_tv_details(query, tid)

    elif data.startswith("m_from_person:"):
        tid = int(data.split(":")[1])
        await _show_movie_details(query, tid)


async def _show_movie_details(query, tmdb_id: int):
    try:
        movie = tmdb.get_movie(tmdb_id)
        cast, directors = tmdb.get_movie_credits(tmdb_id)
        already_have = radarr.movie_exists(tmdb_id)
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    text = (
        f"*{movie.title}* ({movie.year})\n"
        f"⭐ {movie.rating}/10\n\n"
        f"{_shorten(movie.overview, 300)}\n"
    )
    if directors:
        text += f"\n🎬 Dir: {', '.join(directors)}"
    if cast:
        text += f"\n👥 {', '.join(cast)}"

    if already_have:
        text += "\n\n✅ *Ya la tenés en tu biblioteca*"
        keyboard = [[
            InlineKeyboardButton(
                "Ver Cast",
                callback_data=f"cast:{movie.tmdb_id}"
            ),
        ]]
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Agregar a Radarr",
                    callback_data=f"add_movie:{movie.tmdb_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Ver Cast",
                    callback_data=f"cast:{movie.tmdb_id}"
                ),
            ],
        ]

    if movie.poster_url:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        await query.message.reply_photo(movie.poster_url)
    else:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )


async def _add_movie(query, tmdb_id: int):
    try:
        movie = tmdb.get_movie(tmdb_id)
        title = radarr.add_movie(tmdb_id)
        await query.edit_message_text(
            f"✅ *{title}* agregada a Radarr\\.\nPronto va a estar en Plex\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def _show_tv_details(query, tmdb_id: int):
    try:
        show = tmdb.get_tv(tmdb_id)
        already_have = False
        try:
            ext = tmdb.get_tv_external_ids(tmdb_id)
            tvdb_id = ext.get("tvdb_id")
            if tvdb_id:
                already_have = sonarr.series_exists(tvdb_id)
        except Exception:
            pass
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    text = (
        f"*{show.name}* ({show.year})\n"
        f"⭐ {show.rating}/10\n\n"
        f"{_shorten(show.overview, 300)}"
    )

    if already_have:
        text += "\n\n✅ *Ya la tenés en tu biblioteca*"
        keyboard = [
            [
                InlineKeyboardButton(
                    "Temporadas",
                    callback_data=f"seasons:{show.tmdb_id}"
                ),
                InlineKeyboardButton(
                    "Ver Cast",
                    callback_data=f"cast_tv:{show.tmdb_id}"
                ),
            ],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Agregar a Sonarr (completa)",
                    callback_data=f"add_tv:{show.tmdb_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Temporadas",
                    callback_data=f"seasons:{show.tmdb_id}"
                ),
                InlineKeyboardButton(
                    "Ver Cast",
                    callback_data=f"cast_tv:{show.tmdb_id}"
                ),
            ],
        ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _add_tv(query, tmdb_id: int):
    try:
        show = tmdb.get_tv(tmdb_id)
        ext = tmdb.get_tv_external_ids(tmdb_id)
        tvdb_id = ext.get("tvdb_id")
        if not tvdb_id:
            await query.edit_message_text("No tiene TVDB ID.")
            return
        title = sonarr.add_series(tvdb_id, show.name)
        await query.edit_message_text(
            f"✅ *{title}* agregada a Sonarr\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def _show_cast(query, tmdb_id: int):
    try:
        members = tmdb.get_movie_cast(tmdb_id)
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    if not members:
        await query.edit_message_text("No encontré elenco.")
        return

    keyboard = []
    for m in members:
        if m.character == "Director":
            label = f"🎬 {m.name} (Director)"
        else:
            label = f"👤 {m.name} ({m.character})"
        keyboard.append([InlineKeyboardButton(
            label,
            callback_data=f"person_bio:{m.tmdb_id}"
        )])

    keyboard.append([InlineKeyboardButton(
        "Volver",
        callback_data=f"movie:{tmdb_id}"
    )])

    await query.edit_message_text(
        "*Elenco & Dirección:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _show_person_bio(query, person_id: int):
    try:
        person = tmdb.get_person(person_id)
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    name = person.get("name", "Desconocido")
    bio = person.get("biography", "")
    birthday = person.get("birthday", "")
    deathday = person.get("deathday", "")
    birthplace = person.get("place_of_birth", "")
    known = person.get("known_for_department", "")

    text = f"*{name}*"
    if known:
        text += f" — {known}"
    if birthday:
        text += f"\n📅 {birthday}"
        if deathday:
            text += f" — † {deathday}"
    if birthplace:
        text += f"\n📍 {birthplace}"
    if bio:
        text += f"\n\n{_shorten(bio, 400)}"

    keyboard = [
        [InlineKeyboardButton(
            "Buscar películas",
            callback_data=f"person_movies:{person_id}"
        )],
        [InlineKeyboardButton(
            "Buscar series",
            callback_data=f"person_tv:{person_id}"
        )],
    ]

    profile = person.get("profile_path")
    if profile:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        await query.message.reply_photo(
            f"https://image.tmdb.org/t/p/w200{profile}"
        )
    else:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )


async def _show_person_movies(query, person_id: int, page: int = 1):
    try:
        movies = tmdb.get_person_movie_credits(person_id, page=page)
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    if not movies:
        await query.edit_message_text("No encontré películas.")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{'⭐' if m.rating >= 7 else '🎬'} {m.title} ({m.year})",
            callback_data=f"m_from_person:{m.tmdb_id}"
        )]
        for m in movies
    ]

    if len(movies) == 8:
        keyboard.append([InlineKeyboardButton(
            "Mostrar más",
            callback_data=f"person_movies_p:{person_id}:{page + 1}"
        )])

    await query.edit_message_text(
        f"Películas (pág {page}):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _show_tv_cast(query, tmdb_id: int):
    try:
        members = tmdb.get_tv_cast(tmdb_id)
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    if not members:
        await query.edit_message_text("No encontré elenco.")
        return

    keyboard = []
    for m in members:
        if m.character == "Director":
            label = f"🎬 {m.name} (Director)"
        else:
            label = f"👤 {m.name} ({m.character})"
        keyboard.append([InlineKeyboardButton(
            label,
            callback_data=f"person_bio:{m.tmdb_id}"
        )])

    keyboard.append([InlineKeyboardButton(
        "Volver",
        callback_data=f"tv:{tmdb_id}"
    )])

    await query.edit_message_text(
        "*Elenco & Dirección:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _show_tv_seasons(query, tmdb_id: int):
    try:
        seasons = tmdb.get_tv_seasons(tmdb_id)
        ext = tmdb.get_tv_external_ids(tmdb_id)
        tvdb_id = ext.get("tvdb_id")
        existing = sonarr.get_series_season_status(tvdb_id) if tvdb_id else {"found": False, "seasons": []}
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    if not seasons:
        await query.edit_message_text("No encontré temporadas.")
        return

    keyboard = []
    for s in seasons:
        sn = s["season_number"]
        status = ""
        if existing["found"]:
            match = next((es for es in existing["seasons"] if es["season_number"] == sn), None)
            if match:
                if match["has_files"]:
                    status = " ✅"
                elif match["monitored"]:
                    status = " 🔍"
        keyboard.append([InlineKeyboardButton(
            f"📺 {s['name']} ({s['episode_count']} ep.){status}",
            callback_data=f"add_tv_season:{tmdb_id}:{sn}"
        )])

    keyboard.append([InlineKeyboardButton(
        "Volver",
        callback_data=f"tv:{tmdb_id}"
    )])

    header = "*Temporadas:*"
    if existing["found"]:
        header += "\n✅ = ya bajada | 🔍 = buscando"

    await query.edit_message_text(
        header,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _add_tv_season(query, tmdb_id: int, season_num: int):
    try:
        show = tmdb.get_tv(tmdb_id)
        ext = tmdb.get_tv_external_ids(tmdb_id)
        tvdb_id = ext.get("tvdb_id")
        if not tvdb_id:
            await query.edit_message_text("No tiene TVDB ID.")
            return
        title = sonarr.add_series_with_seasons(tvdb_id, [season_num], show.name)
        await query.edit_message_text(
            f"✅ *{title}* T{season_num} agregada\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def _show_person_tv(query, person_id: int, page: int = 1):
    try:
        shows = tmdb.get_person_tv_credits(person_id, page=page)
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return

    if not shows:
        await query.edit_message_text("No encontré series.")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{'⭐' if s.rating >= 7 else '📺'} {s.name} ({s.year})",
            callback_data=f"t_from_person:{s.tmdb_id}"
        )]
        for s in shows
    ]

    if len(shows) == 8:
        keyboard.append([InlineKeyboardButton(
            "Mostrar más",
            callback_data=f"person_tv_p:{person_id}:{page + 1}"
        )])

    await query.edit_message_text(
        f"Series (pág {page}):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
