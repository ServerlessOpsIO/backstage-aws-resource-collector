from typing import List

from mypy_boto3_organizations.type_defs import AccountTypeDef

class AccountType(AccountTypeDef):
    pass

class AccountTypeWithTags(AccountType):
    Tags: List[dict]