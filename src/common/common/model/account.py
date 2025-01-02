from dataclasses import dataclass
from typing import List

from mypy_boto3_organizations.type_defs import AccountTypeDef

@dataclass
class AccountType(AccountTypeDef):
    pass

@dataclass
class AccountTypeWithTags(AccountType):
    Tags: List[dict]