import os
from typing import Callable, Generator

from boto3 import Session
from botocore.client import BaseClient

import pytest
from moto import mock_aws

# AWS mocks
@pytest.fixture()
def mock_aws_credentials() -> None:
    '''Mocked AWS Credentials for moto.'''
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture()
def mocked_aws(mock_aws_credentials):
    '''Mock all AWS interactions'''
    with mock_aws():
        yield

@pytest.fixture()
def mocked_aws_session(mocked_aws) -> Generator[Session, None, None]:
    '''Mock all AWS interactions'''
    yield Session()

@pytest.fixture()
def make_mocked_client(
    mocked_aws_session: Session,
) -> Generator[Callable[[str], BaseClient], None, None]:
    '''Mock an AWS service client'''
    def _make_client(service_name: str) -> BaseClient:
        return mocked_aws_session.client(service_name)    # type: ignore
    yield _make_client