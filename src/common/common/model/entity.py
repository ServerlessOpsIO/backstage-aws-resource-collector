'''ServerlessOps / Backstage Catalog entity'''
from typing import Dict, List, Optional, TypedDict, DefaultDict

class EntityMetaLink(TypedDict):
    url: str
    title: Optional[str]
    icon: Optional[str]
    type: Optional[str]

class EntityMetaLinks(List[EntityMetaLink]): pass

class EntityMeta(TypedDict):
    name: str
    namespace: str
    title: str
    description: str
    annotations: Dict[str, str]
    links: EntityMetaLinks

class EntitySpec(TypedDict):
    owner: str
    system: str
    type: str
    lifecycle: str

class Entity(TypedDict):
    apiVersion: str
    kind: str
    metadata: EntityMeta
    spec: EntitySpec
