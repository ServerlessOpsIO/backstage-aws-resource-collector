from aws_lambda_powertools.utilities.data_classes.common import DictWrapper
from aws_lambda_powertools.utilities.data_classes import (
    EventBridgeEvent
)

class S3CreateBucketEventDRequestParameters(DictWrapper):
    '''Request Parameters for S3 Create Bucket Event'''
    @property
    def bucket_name(self) -> str:
        '''Name of the bucket being created'''
        return self['bucketName']


class S3CreateBucketEventDetail(DictWrapper):
    '''Event detail for S3 Create Bucket Event'''
    @property
    def aws_region(self) -> str:
        '''AWS region where the event originated'''
        return self['awsRegion']

    @property
    def recipient_account_id(self) -> str:
        '''Account ID of the recipient'''
        return self['recipientAccountId']

    @property
    def request_parameters(self) -> S3CreateBucketEventDRequestParameters:
        '''Request parameters'''
        return S3CreateBucketEventDRequestParameters(self['requestParameters'])


class S3CreateBucketEvent(EventBridgeEvent):
    '''Event for S3 Create Bucket Event'''
    @property
    def detail(self) -> S3CreateBucketEventDetail:
        '''Typed event detail for S3 Create Bucket Event'''
        return S3CreateBucketEventDetail(self['detail'])
