from typing import (
    Any,
    AsyncIterable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import httpx
from httpcore import AsyncByteStream, SyncByteStream

URL = Tuple[
    bytes,  # scheme
    bytes,  # host
    Optional[int],  # port
    bytes,  # path
]
Headers = List[Tuple[bytes, bytes]]
Request = Tuple[
    bytes,  # http method
    URL,
    Headers,
    Union[Iterable[bytes], AsyncIterable[bytes]],  # body
]
SyncResponse = Tuple[
    int,  # status code
    Headers,
    SyncByteStream,  # body
    dict,  # ext
]
AsyncResponse = Tuple[
    int,  # status code
    Headers,
    AsyncByteStream,  # body
    dict,  # ext
]
Response = Tuple[
    int,  # status code
    Headers,
    Union[Iterable[bytes], AsyncIterable[bytes]],  # body
    dict,  # ext
]

HeaderTypes = Union[
    httpx.Headers,
    Dict[str, str],
    Dict[bytes, bytes],
    Sequence[Tuple[str, str]],
    Sequence[Tuple[bytes, bytes]],
]

DefaultType = TypeVar("DefaultType", bound=Any)

Kwargs = Dict[str, Any]
URLPatternTypes = Union[str, Pattern[str], URL, httpx.URL]
JSONTypes = Union[str, List, Dict]
ContentDataTypes = Union[bytes, str, JSONTypes, Callable, Exception]
QueryParamTypes = Union[bytes, str, List[Tuple[str, Any]], Dict[str, Any]]
RequestTypes = Union[Request, httpx.Request]
