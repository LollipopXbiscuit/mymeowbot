# (c) adarsh-goel
import os
from os import getenv, environ
from dotenv import load_dotenv



load_dotenv()

class Var(object):
    MULTI_CLIENT = False
    API_ID = int(getenv('API_ID', '0') or '0')
    API_HASH = str(getenv('API_HASH', ''))
    BOT_TOKEN = str(getenv('BOT_TOKEN', ''))
    name = str(getenv('SESSION_NAME', 'filetolinkbot'))
    SLEEP_THRESHOLD = int(getenv('SLEEP_THRESHOLD', '60') or '60')
    WORKERS = int(getenv('WORKERS', '4') or '4')
    BIN_CHANNEL = int(getenv('BIN_CHANNEL', '0') or '0')
    PORT = int(getenv('PORT', '5000') or '5000')
    BIND_ADRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
    PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200") or "1200")
    OWNER_ID = set(int(x) for x in os.environ.get("OWNER_ID", "").split() if x)  
    NO_PORT = bool(getenv('NO_PORT', False))
    APP_NAME = None
    OWNER_USERNAME = str(getenv('OWNER_USERNAME', ''))
    if 'DYNO' in environ:
        ON_HEROKU = True
        APP_NAME = str(getenv('APP_NAME'))
    
    else:
        ON_HEROKU = False
    # Prefer the public hostname supplied by the hosting platform. The bind
    # address (0.0.0.0) is only for listening and cannot be used in a link.
    PUBLIC_DOMAIN = (
        getenv('RAILWAY_PUBLIC_DOMAIN')
        or getenv('REPLIT_DEV_DOMAIN')
        or getenv('REPLIT_DOMAINS')
        or getenv('FQDN')
    )

    if PUBLIC_DOMAIN:
        FQDN = PUBLIC_DOMAIN.replace('https://', '').replace('http://', '').rstrip('/')
        URL = "https://{}/".format(FQDN)
    else:
        FQDN = APP_NAME + '.herokuapp.com' if ON_HEROKU else BIND_ADRESS
        HAS_SSL=bool(getenv('HAS_SSL',False))
        if HAS_SSL:
            URL = "https://{}/".format(FQDN)
        else:
            URL = "http://{}/".format(FQDN)
    DATABASE_URL = str(getenv('MONGODB_URL', getenv('DATABASE_URL', '')))
    UPDATES_CHANNEL = str(getenv('UPDATES_CHANNEL', None))
    BANNED_CHANNELS = list(set(int(x) for x in str(getenv("BANNED_CHANNELS", "-1001362659779")).split() if x))
