# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import re
import time
import math
import logging
import secrets
import mimetypes
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from Adarsh.bot import multi_clients, work_loads, StreamBot
from Adarsh.server.exceptions import FIleNotFound, InvalidHash
from Adarsh import StartTime, __version__
from ..utils.time_format import get_readable_time
from ..utils.custom_dl import ByteStreamer, offset_fix, chunk_size
from Adarsh.utils.render_template import render_page
from Adarsh.vars import Var


routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.username,
            "connected_bots": len(multi_clients),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
            "version": __version__,
        }
    )


@routes.get(r"/dl/{secure_hash}/{filename}", allow_head=True)
async def dl_handler(request: web.Request):
    try:
        secure_hash = request.match_info["secure_hash"]
        filename = request.match_info["filename"]
        
        # Look for the message ID in the database using the hash
        from ..utils.database import Database
        db = Database(Var.DATABASE_URL, Var.name)
        file_data = await db.get_file(secure_hash)
        
        if not file_data:
            return web.Response(text="File not found or expired", status=404)
            
        id = file_data['message_id']
        return await media_streamer(request, id, secure_hash)
    except Exception as e:
        logging.critical(f"Error in stream handler: {e}")
        return web.Response(text=f"Server Error: {str(e)}", status=500)

@routes.get(r"/watch/{id:\d+}/{filename}", allow_head=True)
async def watch_handler(request: web.Request):
    try:
        id = int(request.match_info["id"])
        secure_hash = request.rel_url.query.get("hash")
        return web.Response(text=await render_page(id, secure_hash), content_type='text/html')
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except Exception as e:
        logging.critical(f"Error in stream handler: {e}")
        return web.Response(text=f"Server Error: {str(e)}", status=500)

@routes.get(r"/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            id = int(match.group(2))
        else:
            id_match = re.search(r"(\d+)(?:\/\S+)?", path)
            if id_match:
                id = int(id_match.group(1))
                secure_hash = request.rel_url.query.get("hash")
            else:
                return web.Response(text="Invalid Path", status=400)
        return await media_streamer(request, id, secure_hash)
    except Exception as e:
        logging.critical(f"Error in stream handler: {e}")
        return web.Response(text=f"Server Error: {str(e)}", status=500)

class_cache = {}

async def media_streamer(request: web.Request, id: int, secure_hash: str):
    range_header = request.headers.get("Range", 0)
    
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    if Var.MULTI_CLIENT:
        logging.info(f"Client {index} is now serving {request.remote}")

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logging.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logging.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect
    logging.debug("before calling get_file_properties")
    file_id = await tg_connect.get_file_properties(id)
    logging.debug("after calling get_file_properties")
    
    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash for message with ID {id}")
        raise InvalidHash
    
    file_size = file_id.file_size

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = request.http_range.stop or file_size - 1

    req_length = until_bytes - from_bytes
    new_chunk_size = await chunk_size(req_length)
    offset = await offset_fix(from_bytes, new_chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % new_chunk_size) + 1
    part_count = math.ceil(req_length / new_chunk_size)
    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, new_chunk_size
    )

    mime_type = file_id.mime_type or mimetypes.guess_type(file_id.file_name)[0] or "application/octet-stream"
    file_name = file_id.file_name or f"{secrets.token_hex(2)}.file"
    
    # Use inline for images and videos to support social media previews
    # Social media bots like Discord/Telegram require the URL to look like a file and the server to return 200 OK with correct MIME
    disposition = "inline" if ("image" in mime_type or "video" in mime_type) else "attachment"
    
    headers = {
        "Content-Type": f"{mime_type}",
        "Content-Disposition": f'{disposition}; filename="{file_name}"',
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-cache",
    }
    
    # Set status 200 for social media bots even if they don't send Range header
    status = 200
    if range_header:
        status = 206
    
    return_resp = web.Response(
        status=status,
        body=body,
        headers=headers,
    )

    if return_resp.status == 200:
        return_resp.headers.add("Content-Length", str(file_size))

    return return_resp
