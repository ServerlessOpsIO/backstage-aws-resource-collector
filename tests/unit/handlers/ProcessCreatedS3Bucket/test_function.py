'''Test ProcessCreatedS3Bucket'''
# pylint: disable=redefined-outer-name,unused-argument,protected-access

import json
import os
from time import time
from types import ModuleType
from typing import Generator, List

import jsonschema

import pytest
from pytest_mock import MockerFixture
import requests_mock

import boto3
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.type_defs import BucketTypeDef, TagTypeDef
from moto import mock_aws

from aws_lambda_powertools.utilities.typing import LambdaContext

from common.model.account import AccountTypeWithTags
from common.model.events.s3 import S3CreateBucketEvent, S3CreateBucketEventDetail
from common.test.aws import create_lambda_function_context
from common.util.jwt import AUTH_ENDPOINT, JwtAuth

FN_NAME = 'ProcessCreatedS3Bucket'
DATA_DIR = './data'
FUNC_DATA_DIR = os.path.join(DATA_DIR, 'handlers', FN_NAME)
EVENT = os.path.join(FUNC_DATA_DIR, 'event.json')
EVENT_SCHEMA = os.path.join(FUNC_DATA_DIR, 'event.schema.json')
EVENT_DATA = os.path.join(FUNC_DATA_DIR, 'event-data.json')
EVENT_DATA_SCHEMA = os.path.join(FUNC_DATA_DIR, 'event-data.schema.json')

### Fixtures
# Mock data
@pytest.fixture()
def mock_event_data(e=EVENT_DATA) -> S3CreateBucketEventDetail:
    '''Return event data object'''
    with open(e) as f:
        return S3CreateBucketEventDetail(json.load(f))

@pytest.fixture()
def event_data_schema(schema=EVENT_DATA_SCHEMA):
    '''Return an data schema'''
    with open(schema) as f:
        return json.load(f)

@pytest.fixture()
def mock_event(e=EVENT) -> S3CreateBucketEvent:
    '''Return a function event'''
    with open(e) as f:
        return S3CreateBucketEvent(json.load(f))

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
def mock_s3_client(mocked_aws) -> Generator[S3Client, None, None]:
    '''Mock S3 Client'''
    s3_client = boto3.client('s3')
    yield s3_client

@pytest.fixture()
def mock_s3_bucket(mock_s3_client, mock_event_data) -> BucketTypeDef:
    '''Return a mock S3 Bucket'''
    bucket_name = 'mock-bucket'
    mock_s3_client.create_bucket(
        Bucket=mock_event_data.get('requestParameters')['bucketName'],
    )

    bucket = mock_s3_client.list_buckets(
        Prefix=bucket_name
    ).get('Buckets', [])[0]

    return bucket

@pytest.fixture()
def mock_s3_bucket_tags(mock_s3_client, mock_s3_bucket) -> List[TagTypeDef]:
    mock_s3_client.put_bucket_tagging(
        Bucket=mock_s3_bucket.get('Name'),
        Tagging={
            'TagSet': [
                {'Key': 'org:system', 'Value': 'system-1'},
                {'Key': 'org:domain', 'Value': 'domain-1'},
            ]
        }
    )

    tags = mock_s3_client.get_bucket_tagging(
        Bucket=mock_s3_bucket['Name']
    )
    return tags.get('TagSet', [])


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
    mock_endpoint,
    mock_auth,
    requests_mocker: requests_mock.Mocker,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.ProcessCreatedS3Bucket.function as fn

    # NOTE: use mocker to mock any top-level variables outside of the handler function.
    mocker.patch(
        'src.handlers.ProcessCreatedS3Bucket.function.JWT',
        mock_auth
    )

    mocker.patch(
        'src.handlers.ProcessCreatedS3Bucket.function.CATALOG_ENDPOINT',
        mock_endpoint
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
def test_validate_data(mock_event_data, event_data_schema):
    '''Test event data against schema'''
    jsonschema.Draft7Validator(mock_event_data, event_data_schema)

def test_validate_event(mock_event, event_schema):
    '''Test event against schema'''
    jsonschema.Draft7Validator(mock_event._data, event_schema)


### Code Tests
def test_GetSystemOwnerError(mock_fn: ModuleType):
    '''Test GetSystemOwnerError class'''
    e = mock_fn.GetSystemOwnerError('TestSystem')
    assert str(e) == 'Failed to get owner for system: TestSystem'

def test__create_s3_bucket_entity(
    mock_fn: ModuleType,
    mock_event_data: S3CreateBucketEventDetail,
    mock_event: S3CreateBucketEvent,
    mock_s3_bucket_tags: List[TagTypeDef],
    mock_auth: JwtAuth,
    mocker: MockerFixture
):
    '''Test test__create_s3_bucket_entity function'''
    mocker.patch(
        'src.handlers.ProcessCreatedS3Bucket.function._get_system_owner',
        return_value='owner'
    )

    account_id = mock_event.account
    region = mock_event_data.aws_region
    bucket_name = mock_event_data.request_parameters.bucket_name
    entity = mock_fn._create_s3_bucket_entity(
        account_id,
        region,
        bucket_name,
        mock_s3_bucket_tags,
        mock_auth
    )

    assert entity['kind'] == 'Resource'
    assert entity['metadata']['name'] == 's3-bucket-{}'.format(bucket_name)
    assert entity['metadata']['title'] == bucket_name
    assert entity['metadata']['description'] == 'S3 Bucket in account {}'.format(account_id)
    assert entity['metadata']['annotations']['aws.amazon.com/account-id'] == account_id
    assert entity['metadata']['annotations']['aws.amazon.com/arn'] == 'arn:aws:s3:::{}'.format(bucket_name)
    assert entity['metadata']['annotations']['aws.amazon.com/bucket-name'] == bucket_name
    assert entity['metadata']['annotations']['aws.amazon.com/region'] == region
    assert entity['spec']['system'] == 'system-1'


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


def test__main(
    mock_fn: ModuleType,
    mock_event_data: S3CreateBucketEventDetail,
    mock_s3_client: S3Client,
    mock_s3_bucket: BucketTypeDef,
    mock_s3_bucket_tags: List[TagTypeDef],
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
        'src.handlers.ProcessCreatedS3Bucket.function._get_system_owner',
        return_value='owner'
    )

    mocker.patch(
        'src.handlers.ProcessCreatedS3Bucket.function._get_cross_account_s3_client',
        return_value=mock_s3_client
    )

    mock_fn._main(mock_event_data)


def test_handler(
    mock_fn: ModuleType,
    mock_context: LambdaContext,
    mock_event_data: S3CreateBucketEventDetail,
    mock_event: S3CreateBucketEvent,
    mock_s3_client: S3Client,
    mock_s3_bucket: BucketTypeDef,
    mock_s3_bucket_tags: List[TagTypeDef],
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
        'src.handlers.ProcessCreatedS3Bucket.function._get_system_owner',
        return_value='owner'
    )

    mocker.patch(
        'src.handlers.ProcessCreatedS3Bucket.function._get_cross_account_s3_client',
        return_value=mock_s3_client
    )

    mock_event.raw_event['detail'] = mock_event_data
    mock_fn.handler(mock_event, mock_context)