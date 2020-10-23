import operator
import re
from enum import Enum
from functools import reduce
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Pattern as RegexPattern,
    Sequence,
    Tuple,
    Union,
)
from urllib.parse import urljoin

import httpx

from .types import QueryParamTypes, RequestTypes, URLPatternTypes


class Lookup(Enum):
    EQUAL = "eq"
    EXACT = "exact"
    REGEX = "regex"
    STARTS_WITH = "startswith"
    # TODO: Add more lookups
    # NOT_EQUAL = "ne"
    # RANGE = "range"


class Match:
    def __init__(self, matches: bool, **context: Any) -> None:
        self.matches = matches
        self.context = context

    def __bool__(self):
        return bool(self.matches)

    def __invert__(self):
        self.matches = not self.matches
        return self

    def __repr__(self):  # pragma: nocover
        return f"<Match {self.matches}>"


class Pattern:
    lookups = {Lookup.EQUAL}
    lookup: Lookup
    value: Any

    def __init__(self, value: Any, lookup: Lookup = Lookup.EQUAL) -> None:
        if lookup not in self.lookups:
            raise ValueError(
                f"{lookup.value} is not a valid Lookup for {self.__class__.__name__}"
            )
        self.lookup = lookup
        self.value = self.clean(value)

    def __and__(self, other: "Pattern") -> "Pattern":
        return _And((self, other))

    def __or__(self, other: "Pattern") -> "Pattern":
        return _Or((self, other))

    def __invert__(self):
        return _Invert(self)

    def __repr__(self):  # pragma: nocover
        return f"<{self.__class__.__name__} {repr(self.value)}>"

    def __hash__(self):
        return hash((self.__class__, self.lookup, self.value))

    def clean(self, value: Any) -> Any:
        """
        Clean and return pattern value.
        """
        return value

    def parse(self, request: RequestTypes) -> Any:  # pragma: nocover
        """
        Parse and return request value to match with pattern value.
        """
        raise NotImplementedError()

    def match(self, request: RequestTypes) -> Match:
        value = self.parse(request)
        lookup_method = getattr(self, f"_{self.lookup.value}")
        return lookup_method(value)

    def _eq(self, value: Any) -> Match:
        return Match(value == self.value)

    def _exact(self, value: Any) -> Match:
        return self._eq(value)

    def _regex(self, value: str) -> Match:
        match = self.value.search(value)
        if match is None:
            return Match(False)
        return Match(True, **match.groupdict())

    def _startswith(self, value: str) -> Match:
        return Match(value.startswith(self.value))


class _And(Pattern):
    value: Tuple[Pattern, Pattern]

    def __repr__(self):  # pragma: nocover
        a, b = self.value
        return f"{repr(a)} AND {repr(b)}"

    def match(self, request: RequestTypes) -> Match:
        a, b = self.value
        match1 = a.match(request)
        match2 = b.match(request)
        if match1 and match2:
            return Match(True, **{**match1.context, **match2.context})
        return Match(False)


class _Or(Pattern):
    value: Tuple[Pattern, Pattern]

    def __repr__(self):  # pragma: nocover
        a, b = self.value
        return f"{repr(a)} OR {repr(b)}"

    def match(self, request: RequestTypes) -> Match:
        a, b = self.value
        match = a.match(request)
        if not match:
            match = b.match(request)
        return match


class _Invert(Pattern):
    value: Pattern

    def __repr__(self):  # pragma: nocover
        return f"NOT {repr(self.value)}"

    def match(self, request: RequestTypes) -> Match:
        return ~self.value.match(request)


class Method(Pattern):
    lookups = {Lookup.EQUAL}
    value: str

    def clean(self, value: str) -> str:
        return value.upper()

    def parse(self, request: RequestTypes) -> str:
        if isinstance(request, httpx.Request):
            method = request.method
        else:
            _method, *_ = request
            method = _method.decode("ascii")
        return method


class Scheme(Pattern):
    lookups = {Lookup.EQUAL}
    value: str

    def clean(self, value: str) -> str:
        return value.lower()

    def parse(self, request: RequestTypes) -> str:
        if isinstance(request, httpx.Request):
            scheme = request.url.scheme
        else:
            _, (_scheme, *_), *_ = request
            scheme = _scheme.decode("ascii")
        return scheme


class Host(Pattern):
    lookups = {Lookup.EQUAL}
    value: str

    def clean(self, value: str) -> str:
        return value.lower()

    def parse(self, request: RequestTypes) -> str:
        if isinstance(request, httpx.Request):
            host = request.url.host
        else:
            _, (_, _host, *_), *_ = request
            host = _host.decode("ascii")
        return host.lower()


class Port(Pattern):
    lookups = {Lookup.EQUAL}
    value: Optional[int]

    def parse(self, request: RequestTypes) -> Optional[int]:
        scheme: Optional[str] = None
        if isinstance(request, httpx.Request):
            scheme = request.url.scheme
            port = request.url.port
        else:
            _, (_scheme, _, port, _), *_ = request
            if _scheme:
                scheme = _scheme.decode("ascii")
        port = get_default_port(scheme, port)
        return port


class Path(Pattern):
    lookups = {Lookup.EQUAL, Lookup.REGEX, Lookup.STARTS_WITH}
    value: Union[str, RegexPattern[str]]

    def clean(
        self, value: Union[str, RegexPattern[str]]
    ) -> Union[str, RegexPattern[str]]:
        if self.lookup in (Lookup.EQUAL, Lookup.STARTS_WITH) and isinstance(value, str):
            path = urljoin("/", value)  # Ensure leading slash
            value = httpx.URL(path).path
        elif self.lookup is Lookup.REGEX and isinstance(value, str):
            value = re.compile(value)
        return value

    def parse(self, request: RequestTypes) -> str:
        if isinstance(request, httpx.Request):
            path = request.url.path
        else:
            _, (_, _, _, _path), *_ = request
            _path, _, _ = _path.partition(b"?")
            path = _path.decode("ascii")
        return path


class Params(Pattern):
    lookups = {Lookup.EQUAL}  # TODO: Add support for EXACT
    value: httpx.QueryParams

    def __hash__(self):
        return hash((self.__class__, str(self.value)))

    def clean(self, value: QueryParamTypes) -> httpx.QueryParams:
        return httpx.QueryParams(value)

    def match(self, request: RequestTypes) -> Match:
        if isinstance(request, httpx.Request):
            query = request.url.query
        else:
            _, url, *_ = request
            query = httpx.URL(url).query

        params = httpx.QueryParams(query)  # TODO: Cache params on request?
        params_list = params.multi_items()

        # TODO: Better partial match logic?
        for item in self.value.multi_items():
            if item not in params_list:
                return Match(False)
            params_list.remove(item)

        return Match(True)


class URL(Pattern):
    lookups = {Lookup.EQUAL, Lookup.EXACT, Lookup.REGEX, Lookup.STARTS_WITH}
    value: Union[Pattern, str, RegexPattern[str]]

    def __hash__(self):
        if isinstance(self.value, Pattern):
            return hash(self.value)
        else:
            return super().__hash__()

    def clean(self, value: URLPatternTypes) -> Union[Pattern, str, RegexPattern[str]]:
        if self.lookup is Lookup.EQUAL:
            pattern = None
            if isinstance(value, (str, tuple)):
                value = httpx.URL(value)

            if isinstance(value, httpx.URL):
                patterns: List[Pattern] = []
                port = get_default_port(value.scheme, value.port)
                if value.scheme:
                    patterns.append(Scheme(value.scheme))
                if value.host:
                    patterns.append(Host(value.host))
                if port:
                    patterns.append(Port(port))
                if value._uri_reference.path:  # URL.path always returns "/"
                    patterns.append(Path(value.path))
                if value.query:
                    patterns.append(Params(value.query))
                if patterns:
                    pattern = combine(patterns)

            if pattern is None:
                raise ValueError(f"Invalid url: {value!r}")

            return pattern

        elif self.lookup is Lookup.REGEX and isinstance(value, str):
            return re.compile(value)

        assert isinstance(value, (str, RegexPattern))

        return value

    def parse(self, request: RequestTypes) -> str:
        if isinstance(request, httpx.Request):
            url = str(request.url)
        else:
            _, _url, *_ = request
            url = str(httpx.URL(_url))
        return url

    def match(self, request: RequestTypes) -> Match:
        if isinstance(self.value, Pattern):
            return self.value.match(request)
        else:
            return super().match(request)


class BaseURL(URL):
    lookups = {Lookup.EQUAL}
    value: Pattern

    def clean(self, value: URLPatternTypes) -> Pattern:
        if isinstance(value, RegexPattern):
            raise ValueError("Invalid base url type: {value!r}")

        url = httpx.URL(value)
        if url.is_relative_url:
            raise ValueError("Invalid base url: {value!r}")

        path = url.path
        base_url = url.copy_with(raw_path=None)
        patterns: List[Pattern] = [URL(base_url)]
        if len(path) > 1:
            patterns.append(Path(path, Lookup.STARTS_WITH))  # Leading path pattern

        return combine(patterns)


def M(*patterns: Pattern, **lookups: Any) -> Pattern:
    pattern: Pattern = None

    patterns = tuple(filter(None, patterns))
    if patterns:
        pattern = combine(patterns)

    mapping = {
        "method": Method,
        "scheme": Scheme,
        "host": Host,
        "port": Port,
        "path": Path,
        "params": Params,
        "url": URL,
        "base_url": BaseURL,
    }

    for pattern__lookup, value in lookups.items():
        if not value:
            continue

        pattern_name, __, lookup_value = pattern__lookup.partition("__")
        if pattern_name not in mapping:
            raise ValueError(f"{pattern_name!r} is not a valid Pattern")

        lookup = Lookup.EQUAL if not lookup_value else Lookup(lookup_value)
        _pattern = mapping[pattern_name](value, lookup=lookup)

        if pattern is None:
            pattern = _pattern
        else:
            pattern &= _pattern

    return pattern


def get_default_port(scheme: Optional[str], port: Optional[int]) -> Optional[int]:
    if port:
        return port
    schemes = {"http": 80, "https": 443}
    if scheme in schemes:
        return schemes[scheme]
    return None


def combine(patterns: Sequence[Pattern], op: Callable = operator.and_) -> Pattern:
    return reduce(op, patterns)
