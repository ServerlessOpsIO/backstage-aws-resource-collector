
'''Process S3 Bucket Created event'''
import os
import json
from typing import TYPE_CHECKING, List

import requests

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
)
import boto3

from common.model.entity import Entity, EntityMeta, EntitySpec
from common.model.events.s3 import S3CreateBucketEvent, S3CreateBucketEventDetail
from common.util.jwt import JwtAuth

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import TagTypeDef
    from mypy_boto3_sts.type_defs import CredentialsTypeDef
    from mypy_boto3_sqs.type_defs import SendMessageResultTypeDef

LOGGER = Logger(utc=True)

# AWS
STS_CLIENT = boto3.client('sts')
CROSS_ACCOUNT_IAM_ROLE_NAME = os.environ.get('CROSS_ACCOUNT_IAM_ROLE_NAME', '')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', 'MUST_SET_SQS_QUEUE_URL')

# Catalog
CATALOG_ENDPOINT = os.environ.get('CATALOG_ENDPOINT', 'MUST_SET_CATALOG_ENDPOINT')
CLIENT_ID = os.environ.get('CLIENT_ID', 'MUST_SET_CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'MUST_SET_CLIENT_SECRET')
JWT = JwtAuth(CLIENT_ID, CLIENT_SECRET)


class GetSystemOwnerError(Exception):
    '''Get System Owner Error'''
    def __init__(self, system) -> None:
        super().__init__('Failed to get owner for system: {}'.format(system))


def _get_cross_account_credentials(
    account_id: str,
    role_name: str
) -> 'CredentialsTypeDef':
    '''Return the IAM role for cross-account access'''
    role_arn = 'arn:aws:iam::{}:role/{}'.format(account_id, role_name)
    try:
        response = STS_CLIENT.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ProcessS3Buckets'
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


def _send_queue_message(entity: Entity) -> 'SendMessageResultTypeDef':
    '''Send message to SQS'''
    sqs = boto3.client('sqs')
    r = sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(entity)
    )
    return r


def _create_s3_bucket_entity(
    account_id: str,
    region: str,
    bucket_name: str,
    bucket_tags: List['TagTypeDef'],
    auth: JwtAuth
) -> Entity:
    '''Create an entity for an S3 bucket'''
    # Type says key and value are not required which is interesting. Jumping through hoops to
    # make mypy happy
    tags = {tag.get('Key'): tag.get('Value', 'NO_VALUE') for tag in bucket_tags }
    system = tags.get('org:system', 'UNKNOWN')
    owner = _get_system_owner(system, auth)

    entity_type = 's3-bucket'

    entity_spec = EntitySpec({
        'system': system,
        'owner': owner,
        'type': entity_type,
        'lifecycle': 'created'
    })

    # FIXME: The odds of a resource collision are low enough at our scale that we'll just use
    # the default namespace. eventually we should figure out how to handle this.
    entity_meta = EntityMeta({
        'namespace': 'default',
        'name': '{}-{}'.format(entity_type, bucket_name),
        'title': bucket_name,
        'description': 'S3 Bucket in account {}'.format(account_id),
        'annotations': {
            "io.serverlessops/cloud-provider": "aws",
            'aws.amazon.com/arn': 'arn:aws:s3:::{}'.format(bucket_name),
            'aws.amazon.com/account-id': account_id,
            'aws.amazon.com/region': region,
            'aws.amazon.com/bucket-name': bucket_name,
        }
    })

    entity = Entity({
        'apiVersion': 'backstage.io/v1alpha1',
        'kind': 'Resource',
        'metadata': entity_meta,
        'spec': entity_spec
    })
    return entity


def _get_system_owner(system: str, auth: JwtAuth) -> str:
    '''Return system owner'''
    r = requests.get(
        '/'.join([
            CATALOG_ENDPOINT,
            'default',
            'system',
            system
        ]),
        auth=auth,
        timeout=10
    )

    if not r.ok:
        LOGGER.error('Failed to get system owner', extra={'response': r.text})
        raise GetSystemOwnerError(system)

    return r.json().get('spec', {}).get('owner', 'UNKNOWN')


def _main(event_detail: S3CreateBucketEventDetail) -> None:
    '''Publish account to catalog.'''

    account_id = event_detail.recipient_account_id
    region = event_detail.aws_region
    bucket_name = event_detail.request_parameters.bucket_name

    s3_client = _get_cross_account_s3_client(
        account_id,
        CROSS_ACCOUNT_IAM_ROLE_NAME
    )

    bucket_tags = s3_client.get_bucket_tagging(
        Bucket=bucket_name
    ).get('TagSet', [])

    entity = _create_s3_bucket_entity(account_id, region, bucket_name, bucket_tags, JWT)
    _send_queue_message(entity)



@LOGGER.inject_lambda_context
@event_source(data_class=S3CreateBucketEvent)
def handler(event: S3CreateBucketEvent, _: LambdaContext) -> None:
    '''Event handler'''
    LOGGER.debug('Event', extra={"message_object": event})
    _main(
        event.detail
    )

    return
