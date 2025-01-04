'''JWT Authentication'''
from requests import post
from requests.auth import AuthBase


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

    def __call__(self, r):
        r.headers['Authorization'] = 'Bearer {}'.format(self.token)
        return r