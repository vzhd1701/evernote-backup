from datetime import timedelta

NETWORK_ERROR_RETRY_COUNT = 50
OAUTH_LOCAL_PORT = 10500
OAUTH_HOST = "localhost"
SYNC_CHUNK_MAX_RESULTS = 200
SYNC_MAX_DOWNLOAD_WORKERS = 5
SYNC_DOWNLOAD_CACHE_MEMORY_LIMIT = 256
DATABASE_NAME = "en_backup.db"
BACKEND = "evernote"

SYNC_CHUNK_MAX_RESULTS_SERVER_LIMIT = 256
SYNC_MAX_DOWNLOAD_WORKERS_SANE_LIMIT = 256

TOKEN_REFRESH_SKEW = timedelta(minutes=15)

EVERNOTE_OAUTH_BASE = "https://accounts.evernote.com"
EVERNOTE_TOKEN_URL = f"{EVERNOTE_OAUTH_BASE}/auth/token"
EVERNOTE_AUTHORIZE_URL = f"{EVERNOTE_OAUTH_BASE}/auth/authorize"
EVERNOTE_DISCOVERY_URL = f"{EVERNOTE_OAUTH_BASE}/.well-known/oauth-authorization-server"

EVERNOTE_API_BASE = "https://api.evernote.com"
EVERNOTE_API_USERS_ME_URL = f"{EVERNOTE_API_BASE}/v1/users/me"
EVERNOTE_API_SYNC_DOWNLOAD_URL = f"{EVERNOTE_API_BASE}/sync/v1/download"

DESKTOP_CLIENT_ID = "3FE74DA6-ABC8-4E20-9940-28D589D4E808"
DESKTOP_REDIRECT_URI = "evernote://www.evernote.com/auth/redirect"

OAUTH_SCOPES = ["openid", "profile", "mono_authn_token", "email", "offline_access"]
