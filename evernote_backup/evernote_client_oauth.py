import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, quote, urlparse

import oauth2

from evernote_backup.config import OAUTH_LOCAL_PORT
from evernote_backup.evernote_client import EvernoteClient


class OAuthDeclinedError(Exception):
    """Raise when user cancels authentication"""


class CallbackHandler(BaseHTTPRequestHandler):
    http_codes = {
        "OK": 200,
        "NOT FOUND": 404,
    }

    def do_GET(self):
        response = urlparse(self.path)

        if response.path != "/oauth_callback":
            self.send_response(self.http_codes["NOT FOUND"])
            self.end_headers()
            return

        self.server.callback_response = dict(parse_qsl(response.query))

        self.send_response(self.http_codes["OK"])
        self.end_headers()
        self.wfile.write(
            "<html><head><title>OAuth Callback</title></head>"
            "<body>You can close this tab now...</body></html>".encode("utf-8")
        )

    def log_message(self, *args, **kwargs):
        """Silencing server log"""


class StoppableHTTPServer(HTTPServer):
    def run(self):
        try:  # noqa: WPS501
            self.serve_forever()
        finally:
            self.server_close()


class EvernoteOAuthCallbackHandler(object):
    def __init__(self, oauth_client):
        self.client = oauth_client

        self.server_host = "localhost"
        self.server_port = OAUTH_LOCAL_PORT
        self.oauth_token = None

    def get_oauth_url(self):
        self.oauth_token = self.client.get_request_token(
            f"http://{self.server_host}:{self.server_port}/oauth_callback"
        )

        return self.client.get_authorize_url(self.oauth_token)

    def wait_for_token(self):
        callback = self._wait_for_callback()

        if "oauth_verifier" not in callback:
            raise OAuthDeclinedError

        return self.client.get_access_token(
            oauth_token=callback["oauth_token"],
            oauth_verifier=callback["oauth_verifier"],
            oauth_token_secret=self.oauth_token["oauth_token_secret"],
        )

    def _wait_for_callback(self):
        server_param = (self.server_host, self.server_port)

        callback_server = StoppableHTTPServer(server_param, CallbackHandler)

        callback_server.callback_response = {}

        thread = threading.Thread(target=callback_server.run)
        thread.start()

        try:  # noqa: WPS501
            while not callback_server.callback_response:
                time.sleep(0.1)
        finally:
            callback_server.shutdown()
            thread.join()

        return callback_server.callback_response


class EvernoteOAuthClient(EvernoteClient):
    def __init__(
        self,
        token=None,
        backend=None,
        consumer_key=None,
        consumer_secret=None,
    ):
        super().__init__(token=token, backend=backend)

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def get_authorize_url(self, request_token):
        return "{0}?oauth_token={1}".format(
            self._get_endpoint("OAuth.action"),
            quote(request_token["oauth_token"]),
        )

    def get_request_token(self, callback_url):

        client = self._get_oauth_client()

        request_url = "{0}?oauth_callback={1}".format(
            self._get_endpoint("oauth"), quote(callback_url)
        )

        _, response_content = client.request(request_url, "GET")

        return dict(parse_qsl(response_content.decode("utf-8")))

    def get_access_token(self, oauth_token, oauth_token_secret, oauth_verifier):
        token = oauth2.Token(oauth_token, oauth_token_secret)
        token.set_verifier(oauth_verifier)

        client = self._get_oauth_client(token)

        _, response_content = client.request(self._get_endpoint("oauth"), "POST")
        access_token_dict = dict(parse_qsl(response_content.decode("utf-8")))

        self.token = access_token_dict["oauth_token"]

        return access_token_dict["oauth_token"]

    def _get_oauth_client(self, token=None):
        consumer = oauth2.Consumer(self.consumer_key, self.consumer_secret)

        if token:
            client = oauth2.Client(consumer, token)
        else:
            client = oauth2.Client(consumer)

        return client
