'''JWT Authentication'''
from requests import post
from requests.auth import AuthBase
from time import time


AUTH_ENDPOINT = 'https://auth.serverlessops.io/oauth2/token'

class JwtRequestException(Exception):
    '''JWT Request Exception'''
    def __init__(self):
        super().__init__('Failed to request JWT token.')


class JwtAuth(AuthBase):
    '''JWT Authentication'''
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.expiration = None

    def __call__(self, r):
        self._validate()
        r.headers['Authorization'] = 'Bearer {}'.format(self.token)
        return r

    def _fetch_jwt(self) -> None:
        response = post(
            AUTH_ENDPOINT,
            data={
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        )

        if not response.ok:
            raise JwtRequestException()
        
        self.token = response.json().get('access_token')
        expires_in = response.json().get('expires_in')
        # Current time + expiration seconds - grace period
        self.expiration = int(time()) + response.json().get('expires_in') - 120

    def _validate(self) -> None:
        if (not self.token) or int(time()) > self.expiration:
           self._fetch_jwt() 
            