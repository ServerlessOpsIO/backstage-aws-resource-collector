import os
from typing import TYPE_CHECKING, Generator

import pytest
from pytest_mock import MockerFixture

import boto3
from moto import mock_aws

if TYPE_CHECKING:
    from mypy_boto3_ec2 import EC2Client
    from mypy_boto3_sts import STSClient

from common.util.aws import get_cross_account_credentials, get_cross_account_client

###
# Mocks
###
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
def mock_sts_client(mocked_aws) -> Generator['STSClient', None, None]:
    '''Mock STS Client'''
    sts_client = boto3.client('sts')
    yield sts_client

@pytest.fixture()
def mock_ec2_client(mocked_aws) -> Generator['EC2Client', None, None]:
    '''Mock EC2 Client'''
    ec2_client = boto3.client('ec2')
    yield ec2_client


###
# Tests
###
def test_get_cross_account_client(
    mock_ec2_client: 'EC2Client',
    mocker: MockerFixture
):
    '''Test get_cross_account_client function'''
    account_id = '123456789012'
    role_name = 'TestRole'
    session_name = 'TestSession'
    service_name = 'ec2'

    mocker.patch('common.util.aws.get_cross_account_credentials', return_value={
        'AccessKeyId': 'mock_access_key',
        'SecretAccessKey': 'mock_secret_key',
        'SessionToken': 'mock_session_token',
        'Expiration': 'mock_expiration'
    })

    client = get_cross_account_client(service_name, account_id, role_name, session_name)

    assert client is not None
    assert hasattr(client, 'describe_vpcs')  # Check if the client has a method for EC2 VPCs


def test_get_cross_account_credentials(mock_sts_client: 'STSClient'):
    '''Test get_cross_account_credentials function'''
    account_id = '123456789012'
    role_name = 'TestRole'
    session_name = 'TestSession'

    credentials = get_cross_account_credentials(account_id, role_name, session_name)

    assert 'AccessKeyId' in credentials
    assert 'SecretAccessKey' in credentials
    assert 'SessionToken' in credentials
    assert 'Expiration' in credentials
