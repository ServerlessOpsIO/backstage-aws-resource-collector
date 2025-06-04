'''List Account S3 Buckets'''
import os
import json
from typing import TYPE_CHECKING, List, Sequence

import boto3

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    SQSEvent
)

from common.model.account import AccountTypeWithTags

if TYPE_CHECKING:
    from mypy_boto3_events.type_defs import PutEventsResponseTypeDef, PutEventsRequestEntryTypeDef
    from mypy_boto3_sts.type_defs import CredentialsTypeDef
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import BucketTypeDef
    from mypy_boto3_sqs.type_defs import SendMessageResultTypeDef

LOGGER = Logger(utc=True)

STS_CLIENT = boto3.client('sts')
EB_CLIENT= boto3.client('events')
SQS_CLIENT = boto3.client('sqs')

CROSS_ACCOUNT_IAM_ROLE_NAME = os.environ.get('CROSS_ACCOUNT_IAM_ROLE_NAME', '')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', 'MUST_SET_SQS_QUEUE_URL')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'MUST_SET_EVENT_BUS_NAME')
SERVICE_NAME = os.environ.get('POWERTOOLS_SERVICE_NAME', 'MUST_SET_POWERTOOLS_SERVICE_NAME')

def _get_cross_account_credentials(
    account_id: str,
    role_name: str
) -> 'CredentialsTypeDef':
    '''Return the IAM role for cross-account access'''
    role_arn = f'arn:aws:iam::{account_id}:role/{role_name}'
    try:
        response = STS_CLIENT.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ProcessBucketsResourcecollector'
        )
    except Exception as e:
        LOGGER.exception(e)
        raise e

    return response['Credentials']

def _get_cross_account_s3_client(
    account_id: str,
    role_name: str
) -> 'S3Client':
    '''Return an S3 client with cross-account access'''
    credentials = _get_cross_account_credentials(
        account_id,
        role_name
    )
    client = boto3.client(
        's3',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    return client

def _list_s3_buckets(account_id: str) -> List['BucketTypeDef']:
    '''List S3 buckets in the account'''
    s3_client = _get_cross_account_s3_client(
        account_id,
        CROSS_ACCOUNT_IAM_ROLE_NAME
    )

    buckets = s3_client.list_buckets()

    return buckets.get('Buckets', [])


def _send_queue_message(bucket: 'BucketTypeDef') -> 'SendMessageResultTypeDef':
    '''Send message to SQS'''
    r = SQS_CLIENT.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(bucket, default=str) # Convert CreationDate datetime to string
    )
    return r

def _send_event_bus_messages(buckets: List['BucketTypeDef']) -> 'PutEventsResponseTypeDef':
    '''Send messages to EventBridge'''
    entires: Sequence['PutEventsRequestEntryTypeDef'] = [
        {
            'Source': SERVICE_NAME,
            'DetailType': 'ListAccountS3Buckets',
            'Detail': json.dumps(buckets, default=str),
            'EventBusName': EVENT_BUS_NAME
        } for b in buckets
    ]
    r = EB_CLIENT.put_events(
        Entries=entires
    )
    return r

def _main(account_info: AccountTypeWithTags) -> None:
    '''List S3 buckets in the account'''
    account_id = account_info.get('Id', '')
    s3_buckets = _list_s3_buckets(account_id)

    #for bucket in s3_buckets:
    #    _send_queue_message(bucket)

    if s3_buckets:
        _send_event_bus_messages(s3_buckets)


@LOGGER.inject_lambda_context
@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, _: LambdaContext) -> None:
    '''Event handler'''
    LOGGER.debug('Event', extra={"message_object": event._data})
    for record in event.records:
        account_info = AccountTypeWithTags(**json.loads(record.body))
        _main(account_info)