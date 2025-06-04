'''Test ListAccountS3Buckets'''
# pylint: disable=missing-function-docstring,missing-module-docstring,unused-argument,redefined-outer-name,protected-access

import json
import os
from types import ModuleType
from typing import Generator

import jsonschema

import pytest
from pytest_mock import MockerFixture

import boto3
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.type_defs import BucketTypeDef
from mypy_boto3_sqs import SQSClient
from mypy_boto3_events import EventBridgeClient
from moto import mock_aws

from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from common.model.account import AccountTypeWithTags
from common.test.aws import create_lambda_function_context

FN_NAME = 'ListAccountS3Buckets'
DATA_DIR = './data'
FUNC_DATA_DIR = os.path.join(DATA_DIR, 'handlers', FN_NAME)
EVENT = os.path.join(FUNC_DATA_DIR, 'event.json')
EVENT_SCHEMA = os.path.join(FUNC_DATA_DIR, 'event.schema.json')
EVENT_DATA = os.path.join(FUNC_DATA_DIR, 'event-data.json')
EVENT_DATA_SCHEMA = os.path.join(FUNC_DATA_DIR, 'event-data.schema.json')

### Fixtures
# Mock data
@pytest.fixture()
def mock_event_data(e=EVENT_DATA) -> AccountTypeWithTags:
    '''Return event data object'''
    with open(e) as f:
        return AccountTypeWithTags(**json.load(f))

@pytest.fixture()
def event_data_schema(schema=EVENT_DATA_SCHEMA):
    '''Return a data schema'''
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
def mock_s3_client(mocked_aws) -> Generator[S3Client, None, None]:
    '''Mock S3 Client'''
    s3_client = boto3.client('s3')
    yield s3_client

@pytest.fixture()
def mock_s3_bucket(mock_s3_client) -> BucketTypeDef:
    '''Return a mock S3 Bucket'''
    bucket_name = 'mock-bucket'
    mock_s3_client.create_bucket(Bucket=bucket_name)
    bucket = mock_s3_client.list_buckets().get('Buckets', [])[0]
    return bucket

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

@pytest.fixture()
def mock_eventbridge_client(mocked_aws) -> Generator[EventBridgeClient, None, None]:
    '''Mock EventBridge Client'''
    eb_client = boto3.client('events')
    yield eb_client

@pytest.fixture()
def mock_event_bus_name(mock_eventbridge_client) -> str:
    '''Mock EventBus Name'''
    r = mock_eventbridge_client.create_event_bus(Name='MockEventBus')
    return r['EventBusArn'].split('/')[-1]


# Function
@pytest.fixture()
def mock_context(function_name=FN_NAME):
    '''context object'''
    return create_lambda_function_context(function_name)

@pytest.fixture()
def mock_fn(
    mock_sqs_queue_url: str,
    mock_event_bus_name: str,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.ListAccountS3Buckets.function as fn

    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function.SQS_QUEUE_URL',
        mock_sqs_queue_url
    )

    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function.EVENT_BUS_NAME',
        mock_event_bus_name
    )

    yield fn

### Data validation tests
def test_validate_event_data(mock_event_data, event_data_schema):
    '''Test event data against schema'''
    jsonschema.Draft7Validator(mock_event_data, event_data_schema)

def test_validate_event(mock_event, event_schema):
    '''Test event data against schema'''
    jsonschema.Draft7Validator(mock_event, event_schema)


### Code Tests
def test__get_cross_account_credentials(
    mock_fn: ModuleType,
    mock_event_data: AccountTypeWithTags,
    mocker: MockerFixture
):
    '''Test _get_cross_account_credentials'''
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function.STS_CLIENT.assume_role',
        return_value={'Credentials': {'AccessKeyId': 'a', 'SecretAccessKey': 'b', 'SessionToken': 'c'}}
    )
    creds = mock_fn._get_cross_account_credentials('123456789012', 'role')
    assert 'AccessKeyId' in creds

def test__get_cross_account_s3_client(
    mock_fn: ModuleType,
    mock_event_data: AccountTypeWithTags,
    mocker: MockerFixture
):
    '''Test _get_cross_account_s3_client'''
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function._get_cross_account_credentials',
        return_value={'AccessKeyId': 'a', 'SecretAccessKey': 'b', 'SessionToken': 'c'}
    )
    client = mock_fn._get_cross_account_s3_client('123456789012', 'role')
    assert client is not None

def test__list_s3_buckets(
    mock_fn: ModuleType,
    mock_event_data: AccountTypeWithTags,
    mocker: MockerFixture
):
    '''Test _list_s3_buckets'''
    mock_s3_client = mocker.Mock()
    mock_s3_client.list_buckets.return_value = {'Buckets': [{'Name': 'bucket1'}]}
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function._get_cross_account_s3_client',
        return_value=mock_s3_client
    )
    buckets = mock_fn._list_s3_buckets('123456789012')
    assert buckets == [{'Name': 'bucket1'}]

def test__send_queue_message(
    mock_fn: ModuleType,
    mock_sqs_queue_url: str,
    mock_sqs_client: SQSClient,
    mock_s3_bucket: BucketTypeDef,
    mocker: MockerFixture
):
    '''Test _send_queue_message'''
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function.boto3.client',
        return_value=mock_sqs_client
    )
    response = mock_fn._send_queue_message(mock_s3_bucket)
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200

def test__send_event_bus_messages(
    mock_fn: ModuleType,
    mock_eventbridge_client: EventBridgeClient,
    mock_event_bus_name: str,
    mock_s3_bucket: BucketTypeDef,
    mocker: MockerFixture
):
    '''Test _send_event_bus_messages'''
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function.boto3.client',
        return_value=mock_eventbridge_client
    )
    response = mock_fn._send_event_bus_messages([mock_s3_bucket])
    assert response['FailedEntryCount'] == 0
    assert len(response['Entries']) == 1


def test__send_event_bus_messages_multiple(
    mock_fn: ModuleType,
    mock_eventbridge_client: EventBridgeClient,
    mock_event_bus_name: str,
    mock_s3_bucket: BucketTypeDef,
    mocker: MockerFixture
):
    '''Test _send_event_bus_messages'''
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function.boto3.client',
        return_value=mock_eventbridge_client
    )
    response = mock_fn._send_event_bus_messages([mock_s3_bucket, mock_s3_bucket])
    assert response['FailedEntryCount'] == 0
    assert len(response['Entries']) == 2


def test__main(
    mock_fn: ModuleType,
    mock_event_data: AccountTypeWithTags,
    mocker: MockerFixture
):
    '''Test _main function'''
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function._list_s3_buckets',
        return_value=[{'Name': 'bucket1'}]
    )
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function._send_queue_message',
        return_value={'ResponseMetadata': {'HTTPStatusCode': 200}}
    )
    mock_fn._main(mock_event_data)

def test_handler(
    mock_fn: ModuleType,
    mock_context: LambdaContext,
    mock_event_data: AccountTypeWithTags,
    mock_event: SQSEvent,
    mocker: MockerFixture
):
    '''Test calling handler'''
    mocker.patch(
        'src.handlers.ListAccountS3Buckets.function._main'
    )
    mock_event._data['Records'][0]['body'] = json.dumps(mock_event_data)
    mock_fn.handler(mock_event, mock_context)