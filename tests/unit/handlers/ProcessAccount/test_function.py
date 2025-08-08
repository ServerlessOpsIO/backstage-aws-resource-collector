'''Test ProcessAccount'''
# pylint: disable=redefined-outer-name, protected-access, import-outside-toplevel, unused-argument

import json
from time import time
from types import ModuleType
from typing import Any, Callable, Generator
import jsonschema

import pytest
from pytest_mock import MockerFixture
import requests_mock

from mypy_boto3_sqs import SQSClient

from aws_lambda_powertools.utilities.typing import LambdaContext

from common.model.account import AccountTypeWithTags
from common.util.jwt import AUTH_ENDPOINT, JwtAuth


# AWS
@pytest.fixture()
def mock_sqs_client(make_mocked_client: Callable) -> Generator[SQSClient, None, None]:
    '''Mock SQS Client'''
    yield make_mocked_client('sqs')

@pytest.fixture()
def mock_sqs_queue_url(mock_sqs_client) -> str:
    '''Mock SQS Queue URL'''
    queue = mock_sqs_client.create_queue(QueueName='mock-queue')
    return queue['QueueUrl']


# Requests
@pytest.fixture()
def requests_mocker() -> requests_mock.Mocker:
    '''Return a requests mock'''
    # NOTE: Use as a decerator with Python 3 appears broken so use fixture.
    # ref. https://github.com/pytest-dev/pytest/issues/2749
    return requests_mock.Mocker()

@pytest.fixture()
def mock_endpoint() -> str:
    '''Return a mock endpoint'''
    return 'https://api.example.com/catalog'

@pytest.fixture()
def mock_auth(
    mocker: MockerFixture,
    requests_mocker: requests_mock.Mocker,
) -> Generator[JwtAuth, None, None]:
    '''Yield a JWT Auth object'''
    requests_mocker.register_uri(
        requests_mock.POST,
        AUTH_ENDPOINT,
        status_code=200,
        json={'access_token': 'token'}
    )

    jwt = JwtAuth('clientId', 'clientSecret')
    mocker.patch.object(jwt, 'token', 'jwt-token')
    mocker.patch.object(jwt, 'expiration', int(time()) + 600)

    yield jwt


# Function
@pytest.fixture()
def mock_fn(
    mock_sqs_queue_url,
    mock_endpoint,
    mock_auth,
    requests_mocker: requests_mock.Mocker,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.ProcessAccount.function as fn

    # NOTE: use mocker to mock any top-level variables outside of the handler function.
    mocker.patch(
        'src.handlers.ProcessAccount.function.JWT',
        mock_auth
    )

    mocker.patch(
        'src.handlers.ProcessAccount.function.CATALOG_ENDPOINT',
        mock_endpoint
    )

    mocker.patch(
        'src.handlers.ProcessAccount.function.SQS_QUEUE_URL',
        mock_sqs_queue_url
    )

    # We can also use requests_mocker within tests too if necessary
    with requests_mocker:
        requests_mocker.register_uri(
            requests_mock.ANY,
            requests_mock.ANY,
            status_code=200,
        )
        yield fn


class TestData:
    '''Validate mock data used by tests'''
    def test_validate_data(self, mock_event_data: dict[str, Any], mock_event_data_schema: dict[str, Any]):
        '''Test event against schema'''
        jsonschema.Draft7Validator(mock_event_data, mock_event_data_schema)

    def test_validate_event(self, mock_event: dict[str, Any], mock_event_schema: dict[str, Any]):
        '''Test event against schema'''
        jsonschema.Draft7Validator(mock_event, mock_event_schema)


class TestCode:
    '''Code tests'''
    def test_GetSystemOwnerError(self, mock_fn: ModuleType):
        '''Test GetSystemOwnerError class'''
        e = mock_fn.GetSystemOwnerError('TestSystem')
        assert str(e) == 'Failed to get owner for system: TestSystem'

    def test__get_entity_data(
        self,
        mock_fn: ModuleType,
        mock_event_data: AccountTypeWithTags,
        mock_auth: JwtAuth,
        mocker: MockerFixture
    ):
        '''Test _get_entity_data function'''
        mocker.patch(
            'src.handlers.ProcessAccount.function._get_system_owner',
            return_value='owner'
        )
        entity = mock_fn._get_entity_data(mock_event_data, mock_auth)
        assert entity['metadata']['name'] == 'aws-{}'.format(mock_event_data.get('Id'))
        assert entity['metadata']['title'] == mock_event_data.get('Id')
        assert entity['metadata']['description'] == mock_event_data.get('Name')
        assert entity['spec']['owner'] == 'owner'
        assert entity['spec']['type'] == 'cloud-account'
        assert entity['spec']['lifecycle'] == 'ACTIVE'

    def test__get_system_owner(
        self,
        mock_fn: ModuleType,
        mock_auth: AccountTypeWithTags,
        requests_mocker: requests_mock.Mocker,
    ):
        '''Test _get_system_owner function'''
        requests_mocker.register_uri(
            requests_mock.GET,
            requests_mock.ANY,
            status_code=200,
            json={'spec': {'owner': 'owner'}}
        )
        owner = mock_fn._get_system_owner('mock_system', mock_auth,)
        assert owner == 'owner'

    def test__get_system_owner_fails(
        self,
        mock_fn: ModuleType,
        mock_auth: AccountTypeWithTags,
        requests_mocker: requests_mock.Mocker,
    ):
        '''Test _get_system_owner function'''
        requests_mocker.register_uri(
            requests_mock.GET,
            requests_mock.ANY,
            status_code=403,
        )
        with pytest.raises(mock_fn.GetSystemOwnerError):
            mock_fn._get_system_owner('mock_system', mock_auth,)


    def test__send_queue_message(
        self,
        mock_fn: ModuleType,
        mock_event_data: AccountTypeWithTags,
    ):
        '''Test _send_queue_message function'''
        response = mock_fn._send_queue_message(mock_event_data)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200


    def test__main(
        self,
        mock_fn: ModuleType,
        mock_event_data: AccountTypeWithTags,
        mocker: MockerFixture
    ):
        '''Test _main function'''
        mocker.patch.object(
            mock_fn,
            'JwtAuth',
            client_id='clientId',
            client_secret='clientSecret',
            token='token'
        )

        mocker.patch(
            'src.handlers.ProcessAccount.function._get_system_owner',
            return_value='owner'
        )

        mock_fn._main(mock_event_data)


    def test_handler(
        self,
        lambda_function_name: str,
        mock_fn: ModuleType,
        mock_context: Callable[[str], LambdaContext],
        mock_event_data: AccountTypeWithTags,
        mock_event: dict[str, Any],
        mocker: MockerFixture
    ):
        '''Test calling handler'''
        # Call the function
        mocker.patch.object(
            mock_fn,
            'JwtAuth',
            client_id='clientId',
            client_secret='clientSecret',
            token='token'
        )

        mocker.patch(
            'src.handlers.ProcessAccount.function._get_system_owner',
            return_value='owner'
        )

        mock_event['Records'][0]['body'] = json.dumps(mock_event_data)
        mock_fn.handler(mock_event, mock_context(lambda_function_name))