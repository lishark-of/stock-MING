from __future__ import annotations

from contextvars import ContextVar, Token
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar, cast


P = ParamSpec("P")
R = TypeVar("R")

_NO_REQUEST_CACHE = object()
_IN_PROGRESS = object()
_request_cache: ContextVar[object] = ContextVar(
    "command_center_request_local_read_cache",
    default=_NO_REQUEST_CACHE,
)


def begin_request_local_memo() -> Token[object]:
    """Start an isolated read memo for one synchronous cache packet build."""

    return _request_cache.set({})


def end_request_local_memo(token: Token[object]) -> None:
    _request_cache.reset(token)


def request_local_memo_scope(func: Callable[P, R]) -> Callable[P, R]:
    """Give each invocation a fresh memo and always discard it afterward."""

    @wraps(func)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        token = begin_request_local_memo()
        try:
            return func(*args, **kwargs)
        finally:
            end_request_local_memo(token)

    return wrapped


def memoize_request_local_read(key: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Reuse a no-argument local read only inside an active request scope.

    Calls outside ``request_local_memo_scope`` retain their original behaviour.
    Exceptions are never cached. A re-entrant call also falls through to the
    original function so this helper cannot turn an existing dependency cycle
    into a partially initialized cache value.
    """

    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            cache_value = _request_cache.get()
            if cache_value is _NO_REQUEST_CACHE or args or kwargs:
                return func(*args, **kwargs)
            cache = cast(dict[str, Any], cache_value)
            cached = cache.get(key, _NO_REQUEST_CACHE)
            if cached is not _NO_REQUEST_CACHE and cached is not _IN_PROGRESS:
                return cast(R, cached)
            if cached is _IN_PROGRESS:
                return func(*args, **kwargs)
            cache[key] = _IN_PROGRESS
            try:
                result = func(*args, **kwargs)
            except BaseException:
                cache.pop(key, None)
                raise
            cache[key] = result
            return result

        return wrapped

    return decorate
