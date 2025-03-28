'''Test ProcessVpcs'''
import json
import jsonschema
import os
from time import time
from types import ModuleType
from typing import Generator, List

import pytest
from pytest_mock import MockerFixture
import requests_mock

import boto3
from mypy_boto3_ec2 import EC2Client
from mypy_boto3_ec2.type_defs import VpcTypeDef
from mypy_boto3_sqs import SQSClient
from moto import mock_aws

from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from common.model.account import AccountTypeWithTags
from common.test.aws import create_lambda_function_context
from common.util.jwt import AUTH_ENDPOINT, JwtAuth

FN_NAME = 'ProcessVpcs'
DATA_DIR = './data'
FUNC_DATA_DIR = os.path.join(DATA_DIR, 'handlers', FN_NAME)
EVENT = os.path.join(FUNC_DATA_DIR, 'event.json')
EVENT_SCHEMA = os.path.join(FUNC_DATA_DIR, 'event.schema.json')
DATA = os.path.join(FUNC_DATA_DIR, 'data.json')
DATA_SCHEMA = os.path.join(FUNC_DATA_DIR, 'data.schema.json')

### Fixtures
# Mock data
@pytest.fixture()
def mock_data(e=DATA) -> AccountTypeWithTags:
    '''Return event data object'''
    with open(e) as f:
        return AccountTypeWithTags(**json.load(f))

@pytest.fixture()
def data_schema(schema=DATA_SCHEMA):
    '''Return an data schema'''
    with open(schema) as f:
        return json.load(f)

@pytest.fixture()
def mock_event(e=EVENT) -> SQSEvent:
    '''Return a function event'''
    with open(e) as f:
        return SQSEvent(json.load(f))

@pytest.fixture()
def event_schema(schema=EVENT_SCHEMA):
    '''Return an event schema'''
    with open(schema) as f:
        return json.load(f)


# AWS
@pytest.fixture()
def aws_credentials() -> None:
    '''Mocked AWS Credentials for moto.'''
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture()
def mocked_aws(aws_credentials):
    '''Mock all AWS interactions'''
    with mock_aws():
        yield

@pytest.fixture()
def mock_ec2_client(mocked_aws) -> Generator[EC2Client, None, None]:
    '''Mock ECS Client'''
    ec2_client = boto3.client('ec2')
    yield ec2_client

@pytest.fixture()
def mock_vpc(mock_ec2_client) -> VpcTypeDef:
    '''Return a mock VPC'''
    vpc_id = mock_ec2_client.create_vpc(
        CidrBlock='10.0.0.0/24',
    ).get('Vpc', {}).get('VpcId', '')
    mock_ec2_client.create_tags(
        Resources=[vpc_id],
        Tags=[{'Key': 'org:system', 'Value': 'mock-system'}]
    )

    vpc = mock_ec2_client.describe_vpcs(
        VpcIds=[vpc_id]
    ).get('Vpcs', [])[0]
    return vpc


@pytest.fixture()
def mock_sqs_client(mocked_aws) -> Generator[SQSClient, None, None]:
    '''Mock SQS Client'''
    sqs_client = boto3.client('sqs')
    yield sqs_client

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
def mock_context(function_name=FN_NAME):
    '''context object'''
    return create_lambda_function_context(function_name)

@pytest.fixture()
def mock_fn(
    mock_sqs_queue_url,
    mock_endpoint,
    mock_auth,
    requests_mocker: requests_mock.Mocker,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.ProcessVpcs.function as fn

    # NOTE: use mocker to mock any top-level variables outside of the handler function.
    mocker.patch(
        'src.handlers.ProcessVpcs.function.JWT',
        mock_auth
    )

    mocker.patch(
        'src.handlers.ProcessVpcs.function.CATALOG_ENDPOINT',
        mock_endpoint
    )

    mocker.patch(
        'src.handlers.ProcessVpcs.function.SQS_QUEUE_URL',
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


### Data validation tests
def test_validate_data(mock_data, data_schema):
    '''Test event against schema'''
    jsonschema.Draft7Validator(mock_data, data_schema)

def test_validate_event(mock_event, event_schema):
    '''Test event against schema'''
    jsonschema.Draft7Validator(mock_event._data, event_schema)


### Code Tests
def test_GetSystemOwnerError(mock_fn: ModuleType):
    '''Test GetSystemOwnerError class'''
    e = mock_fn.GetSystemOwnerError('TestSystem')
    assert str(e) == 'Failed to get owner for system: TestSystem'

def test__create_vpc_entity(
    mock_fn: ModuleType,
    mock_vpc: VpcTypeDef,
    mock_auth: JwtAuth,
    mocker: MockerFixture
):
    '''Test _get_entity_data function'''
    mocker.patch(
        'src.handlers.ProcessVpcs.function._get_system_owner',
        return_value='owner'
    )

    vpc_id = mock_vpc.get('VpcId')
    account_id = '123456789012'
    region = 'us-east-1'

    entity = mock_fn._create_vpc_entity(mock_vpc, account_id, region, 'MockSystem', mock_auth)
    assert entity['kind'] == 'Resource'
    assert entity['metadata']['name'] == 'ec2-vpc-{}'.format(vpc_id)
    assert entity['metadata']['title'] == vpc_id
    assert entity['metadata']['description'] == 'VPC {} in account {}'.format(vpc_id, account_id)
    assert entity['metadata']['annotations']['aws.amazon.com/account-id'] == account_id
    assert entity['metadata']['annotations']['aws.amazon.com/arn'] == 'arn:aws:ec2:{}:{}:vpc/{}'.format(region, account_id, vpc_id)
    assert entity['metadata']['annotations']['aws.amazon.com/owner-account-id'] == mock_vpc.get('OwnerId', 'UNKNOWN')
    assert entity['metadata']['annotations']['aws.amazon.com/region'] == region


def test__get_system_owner(
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
    mock_fn: ModuleType,
    mock_data: AccountTypeWithTags,
):
    '''Test _send_queue_message function'''
    response = mock_fn._send_queue_message(mock_data)
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200


def test__main(
    mock_fn: ModuleType,
    mock_data: AccountTypeWithTags,
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
        'src.handlers.ProcessVpcs.function._get_system_owner',
        return_value='owner'
    )

    mock_fn._main(mock_data)


def test_handler(
    mock_fn: ModuleType,
    mock_context: LambdaContext,
    mock_data: AccountTypeWithTags,
    mock_event: SQSEvent,
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
        'src.handlers.ProcessVpcs.function._get_system_owner',
        return_value='owner'
    )

    mock_event._data['Records'][0]['body'] = json.dumps(mock_data)
    mock_fn.handler(mock_event, mock_context)