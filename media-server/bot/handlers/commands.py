from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..auth import ADMIN_CALLBACK_PREFIXES, admin_required, is_admin
from ..services import radarr, sonarr, tmdb, qbittorrent

# Authorization: every update already passed auth.gate (registered in main.py),
# so handlers here only need to check for admin-only actions.

MOVIES_PER_PAGE = 8
MOVIES_LIST_PAGE_SIZE = 30


def _shorten(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3].rstrip() + "..."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "CineBot — tu servidor de pelis en casa.\n\n"
        "/search <película> — buscar película\n"
        "/tv <serie> — buscar serie\n"
        "/person <nombre> — buscar actor/director\n"
        "/status — cola de descargas (Radarr/Sonarr)\n"
        "/downloads — torrents en qBittorrent\n"
        "/library — estadísticas de la biblioteca\n"
        "/movies [texto] — listar/buscar en tu biblioteca de películas\n"
        "/recent — últimas películas y series agregadas\n"
        "/upcoming — próximos estrenos y episodios\n"
        "/help — ayuda"
    )
    if is_admin(update):
        text += (
            "\n\nAdmin\n"
            "/delete <título> — eliminar de la biblioteca\n"
            "/adduser <id> [nombre] — autorizar usuario\n"
            "/removeuser <id> — quitar acceso\n"
            "/users — usuarios autorizados"
        )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Comandos*\n"
        "/search \\<película\\> — buscar película en TMDB\n"
        "/tv \\<serie\\> — buscar serie en TMDB\n"
        "/person \\<nombre\\> — buscar actor o director\n"
        "/status — cola de descargas \\(Radarr/Sonarr\\)\n"
        "/downloads — torrents en qBittorrent\n"
        "/library — estadísticas de la biblioteca\n"
        "/movies \\[texto\\] — listar/buscar películas de tu biblioteca\n"
        "/recent — últimas películas y series agregadas\n"
        "/upcoming — próximos estrenos y episodios\n"
    )
    if is_admin(update):
        text += (
            "\n*Admin*\n"
            "/delete \\<título\\> — eliminar contenido de la biblioteca\n"
            "/downloads — además permite pausar/borrar torrents\n"
            "/adduser \\<id\\> \\[nombre\\] — autorizar un usuario\n"
            "/removeuser \\<id\\> — quitar acceso\n"
            "/users — listar usuarios autorizados\n"
        )
    text += (
        "\n*Flujo típico:*\n"
        "1\\. `/search inception`\n"
        "2\\. Tocás un resultado\n"
        "3\\. Tocás *Agregar a Radarr*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


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


def _fmt_size(b: int) -> str:
    if b >= 1_099_511_627_776:
        return f"{b / 1_099_511_627_776:.1f} TB"
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.0f} MB"
    return f"{b / 1024:.0f} KB"


async def library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ms = radarr.get_library_stats()
        ss = sonarr.get_library_stats()
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    lines = [
        "📚 *Biblioteca*\n",
        "🎬 *Películas*",
        f"  Total: {ms['total']}",
        f"  Descargadas: {ms['has_file']}",
        f"  Monitoreadas: {ms['monitored']}",
        f"  Espacio: {_fmt_size(ms['size_bytes'])}",
        "",
        "📺 *Series*",
        f"  Total: {ss['total']}",
        f"  Monitoreadas: {ss['monitored']}",
        f"  Episodios: {ss['have_eps']}/{ss['total_eps']}",
        f"  Espacio: {_fmt_size(ss['size_bytes'])}",
        "",
        f"💾 *Total:* {_fmt_size(ms['size_bytes'] + ss['size_bytes'])}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        movies = radarr.get_recent_movies(5)
        series = sonarr.get_recent_series(5)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    lines = ["🆕 *Agregado recientemente*\n"]

    if movies:
        lines.append("🎬 *Películas*")
        for m in movies:
            date_str = m["added"][:10]
            lines.append(f"  {m['title']} ({m['year']}) — {date_str}")

    if series:
        lines.append("\n📺 *Series*")
        for s in series:
            date_str = s["added"][:10]
            seasons = f"{s['season_count']} temp." if s["season_count"] else ""
            lines.append(f"  {s['title']} ({s['year']}) {seasons} — {date_str}")

    if not movies and not series:
        lines.append("Nada agregado recientemente.")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        torrents = qbittorrent.get_torrents()
        transfer = qbittorrent.get_main_data()
    except Exception as e:
        await update.message.reply_text(f"Error conectando a qBittorrent: {e}")
        return

    if not torrents:
        await update.message.reply_text("No hay torrents activos.")
        return

    dl_speed = qbittorrent.format_speed(transfer.get("dl_info_speed", 0))
    up_speed = qbittorrent.format_speed(transfer.get("up_info_speed", 0))
    lines = [f"⬇️ {dl_speed}  ⬆️ {up_speed}\n"]

    show_controls = is_admin(update)
    keyboard = []
    for t in torrents[:10]:
        state = t.get("state", "unknown")
        icon = qbittorrent.STATE_ICON.get(state, "❓")
        name = t.get("name", "?")
        if len(name) > 30:
            name = name[:27] + "..."
        pct = int(t.get("progress", 0) * 100)
        size = qbittorrent.format_size(t.get("size", 0))
        lines.append(f"{icon} {name}")
        lines.append(f"   {pct}% · {size} · {state}")

        h = t.get("hash", "")
        if h and show_controls:
            keyboard.append([
                InlineKeyboardButton(
                    f"⏸ {name[:20]}" if state == "downloading" else f"▶️ {name[:20]}",
                    callback_data=f"qbt_toggle:{h}:{state}"
                ),
                InlineKeyboardButton("🗑", callback_data=f"qbt_delete:{h}"),
            ])

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )


async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        movies = radarr.get_upcoming_movies(60)
        episodes = sonarr.get_upcoming_episodes(7)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    lines = ["📅 *Próximamente*\n"]

    if movies:
        lines.append("🎬 *Películas (próx. 60 días)*")
        type_label = {"digitalRelease": "digital", "physicalRelease": "físico", "inCinemas": "cines"}
        for m in movies:
            label = type_label.get(m["release_type"], m["release_type"])
            lines.append(f"  {m['title']} ({m['year']}) — {m['release_date']} ({label})")

    if episodes:
        lines.append("\n📺 *Episodios esta semana*")
        for ep in episodes:
            ep_str = f"S{ep['season']:02d}E{ep['episode']:02d}"
            lines.append(f"  {ep['series']} {ep_str} — {ep['air_date']}")

    if not movies and not episodes:
        lines.append("Nada en el radar por ahora.")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        movies = radarr.get_movies_list()
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    query = " ".join(context.args).lower() if context.args else None
    if query:
        movies = [m for m in movies if query in m["title"].lower()]

    movies.sort(key=lambda m: m["title"].lower())

    if not movies:
        msg = f"No encontré películas para \"{query}\"." if query else "No hay películas en la biblioteca."
        await update.message.reply_text(msg)
        return

    if query:
        # Filtered search: single message, no pagination
        lines = [f"🎬 *Resultados para \"{query}\"* ({len(movies)}):\n"]
        for m in movies[:50]:
            icon = "✅" if m["has_file"] else "⬇️"
            lines.append(f"{icon} {m['title']} ({m['year']})")
        if len(movies) > 50:
            lines.append(f"\n... y {len(movies) - 50} más. Afiná la búsqueda.")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        return

    await _send_movies_page(update.message, movies, page=1)


async def _send_movies_page(target, movies: list[dict], page: int, edit: bool = False):
    start = (page - 1) * MOVIES_LIST_PAGE_SIZE
    end = start + MOVIES_LIST_PAGE_SIZE
    chunk = movies[start:end]
    total_pages = (len(movies) + MOVIES_LIST_PAGE_SIZE - 1) // MOVIES_LIST_PAGE_SIZE
    has_file_count = sum(1 for m in movies if m["has_file"])

    lines = [f"🎬 *Películas* — pág {page}/{total_pages} ({has_file_count}/{len(movies)} descargadas)\n"]
    for m in chunk:
        icon = "✅" if m["has_file"] else "⬇️"
        lines.append(f"{icon} {m['title']} ({m['year']})")

    text = "\n".join(lines)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"movies_p:{page - 1}"))
    if end < len(movies):
        nav.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"movies_p:{page + 1}"))
    markup = InlineKeyboardMarkup([nav]) if nav else None

    if edit:
        await target.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await target.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


@admin_required
async def delete_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /delete <título>\n"
            "Busca en películas y series para eliminar."
        )
        return

    query = " ".join(context.args).lower()
    try:
        movies = radarr.get_movies_list()
        series = sonarr.get_series_list()
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    matched_movies = [m for m in movies if query in m["title"].lower()]
    matched_series = [s for s in series if query in s["title"].lower()]

    if not matched_movies and not matched_series:
        await update.message.reply_text(f"No encontré nada con \"{query}\".")
        return

    keyboard = []
    for m in matched_movies[:5]:
        label = f"🎬 {m['title']} ({m['year']})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"del_movie:{m['id']}")])
    for s in matched_series[:5]:
        label = f"📺 {s['title']} ({s['year']})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"del_series:{s['id']}")])

    await update.message.reply_text(
        f"Resultados para *{query}* — tocá para eliminar:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if data.startswith(ADMIN_CALLBACK_PREFIXES) and not is_admin(update):
        await query.answer("Solo el admin puede hacer esto.", show_alert=True)
        return

    await query.answer()

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

    elif data.startswith("movies_p:"):
        page = int(data.split(":")[1])
        try:
            movies = radarr.get_movies_list()
        except Exception as e:
            await query.edit_message_text(f"Error: {e}")
            return
        movies.sort(key=lambda m: m["title"].lower())
        await _send_movies_page(query, movies, page=page, edit=True)

    elif data.startswith("qbt_toggle:"):
        parts = data.split(":")
        h = parts[1]
        state = parts[2]
        try:
            if state == "downloading":
                qbittorrent.pause_torrent(h)
                await query.edit_message_text("⏸ Torrent pausado.")
            else:
                qbittorrent.resume_torrent(h)
                await query.edit_message_text("▶️ Torrent reanudado.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data.startswith("qbt_delete:"):
        h = data.split(":")[1]
        keyboard = [[
            InlineKeyboardButton("Eliminar torrent (mantener archivos)", callback_data=f"qbt_del_nofiles:{h}"),
            InlineKeyboardButton("Eliminar TODO (torrent + archivos)", callback_data=f"qbt_del_files:{h}"),
        ]]
        await query.edit_message_text(
            "¿Cómo querés eliminar?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("qbt_del_nofiles:"):
        h = data.split(":")[1]
        try:
            qbittorrent.delete_torrent(h, delete_files=False)
            await query.edit_message_text("🗑 Torrent eliminado (archivos conservados).")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data.startswith("qbt_del_files:"):
        h = data.split(":")[1]
        try:
            qbittorrent.delete_torrent(h, delete_files=True)
            await query.edit_message_text("🗑 Torrent y archivos eliminados.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data.startswith("del_movie:"):
        rid = int(data.split(":")[1])
        keyboard = [[
            InlineKeyboardButton("Sí, eliminar", callback_data=f"del_movie_confirm:{rid}"),
            InlineKeyboardButton("Cancelar", callback_data="del_cancel"),
        ]]
        await query.edit_message_text(
            "¿Confirmar eliminación de la película? Se borran los archivos.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("del_movie_confirm:"):
        rid = int(data.split(":")[1])
        try:
            radarr.delete_movie(rid, delete_files=True)
            await query.edit_message_text("🗑 Película eliminada de Radarr y disco.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data.startswith("del_series:"):
        sid = int(data.split(":")[1])
        keyboard = [[
            InlineKeyboardButton("Sí, eliminar", callback_data=f"del_series_confirm:{sid}"),
            InlineKeyboardButton("Cancelar", callback_data="del_cancel"),
        ]]
        await query.edit_message_text(
            "¿Confirmar eliminación de la serie? Se borran los archivos.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("del_series_confirm:"):
        sid = int(data.split(":")[1])
        try:
            sonarr.delete_series(sid, delete_files=True)
            await query.edit_message_text("🗑 Serie eliminada de Sonarr y disco.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data == "del_cancel":
        await query.edit_message_text("Cancelado.")


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
