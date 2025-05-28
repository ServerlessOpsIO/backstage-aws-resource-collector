'''ServerlessOps / Backstage Catalog entity'''
from typing import Dict, List, Literal, NotRequired, TypedDict

class EntityMetaLink(TypedDict):
    url: str
    title: NotRequired[str]
    icon: NotRequired[str]
    type: NotRequired[str]

class EntityMetaLinks(List[EntityMetaLink]): pass

class EntityMeta(TypedDict):
    name: str
    namespace: str
    title: str
    description: str
    annotations: Dict[str, str]
    links: NotRequired[EntityMetaLinks]

class EntitySpec(TypedDict):
    owner: str
    system: str
    type: str
    lifecycle: Literal['created', 'deleted', 'unknown']

class Entity(TypedDict):
    apiVersion: str
    kind: str
    metadata: EntityMeta
    spec: EntitySpec
