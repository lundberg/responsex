from contextlib import ExitStack as does_not_raise

import httpcore
import httpx
import pytest

import respx
from respx import ASGIHandler, WSGIHandler
from respx.mocks import Mocker
from respx.models import AllMockedAssertionError
from respx.router import MockRouter


@respx.mock
async def test_decorating_test(client):
    assert respx.calls.call_count == 0
    respx.calls.assert_not_called()
    request = respx.route(url="https://foo.bar/", name="home").respond(202)
    response = await client.get("https://foo.bar/")
    assert request.called is True
    assert response.status_code == 202
    assert respx.calls.call_count == 1
    assert respx.routes["home"].call_count == 1
    respx.calls.assert_called_once()
    respx.routes["home"].calls.assert_called_once()


async def test_mock_request_fixture(client, my_mock):
    assert respx.calls.call_count == 0
    assert my_mock.calls.call_count == 0
    response = await client.get("https://httpx.mock/")
    request = my_mock.routes["index"]
    assert request.called is True
    assert response.is_error
    assert response.status_code == 404
    assert respx.calls.call_count == 0
    assert my_mock.calls.call_count == 1


async def test_mock_single_session_fixture(client, mocked_foo):
    current_foo_call_count = mocked_foo.calls.call_count
    response = await client.get("https://foo.api/api/bar/")
    request = mocked_foo.routes["bar"]
    assert request.called is True
    assert response.status_code == 200
    assert mocked_foo.calls.call_count == current_foo_call_count + 1


async def test_mock_multiple_session_fixtures(client, mocked_foo, mocked_ham):
    current_foo_call_count = mocked_foo.calls.call_count
    current_ham_call_count = mocked_ham.calls.call_count

    response = await client.get("https://foo.api/api/")
    request = mocked_foo.routes["index"]
    assert request.called is True
    assert response.status_code == 202

    response = await client.get("https://ham.api/")
    request = mocked_foo.routes["index"]
    assert request.called is True
    assert response.status_code == 200

    assert mocked_foo.calls.call_count == current_foo_call_count + 1
    assert mocked_ham.calls.call_count == current_ham_call_count + 1


def test_global_sync_decorator():
    @respx.mock
    def test():
        assert respx.calls.call_count == 0
        request = respx.get("https://foo.bar/") % httpx.Response(202)
        response = httpx.get("https://foo.bar/")
        assert request.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 1

    assert respx.calls.call_count == 0
    test()
    assert respx.calls.call_count == 0


async def test_global_async_decorator(client):
    @respx.mock
    async def test():
        assert respx.calls.call_count == 0
        request = respx.get("https://foo.bar/") % httpx.Response(202)
        response = await client.get("https://foo.bar/")
        assert request.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 1

    assert respx.calls.call_count == 0
    await test()
    assert respx.calls.call_count == 0


@pytest.mark.parametrize("using", ["httpcore", "httpx"])
def test_local_sync_decorator(using):
    @respx.mock(using=using)
    def test(respx_mock):
        assert respx.calls.call_count == 0
        request = respx_mock.get("https://foo.bar/") % 202
        response = httpx.get("https://foo.bar/")
        assert request.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 0
        assert respx_mock.calls.call_count == 1

        with pytest.raises(AllMockedAssertionError):
            httpx.post("https://foo.bar/")

    assert respx.calls.call_count == 0
    test()
    assert respx.calls.call_count == 0


@pytest.mark.parametrize("using", ["httpcore", "httpx"])
async def test_local_async_decorator(client, using):
    @respx.mock(using=using)
    async def test(respx_mock):
        assert respx.calls.call_count == 0

        stream = httpx.ByteStream(b"foobar")
        request = respx_mock.get("https://foo.bar/").mock(
            return_value=httpx.Response(202, stream=stream)
        )

        response = await client.get("https://foo.bar/")
        assert request.called is True
        assert response.status_code == 202
        assert response.content == b"foobar"
        assert respx.calls.call_count == 0
        assert respx_mock.calls.call_count == 1

        with pytest.raises(AllMockedAssertionError):
            httpx.post("https://foo.bar/")

    assert respx.calls.call_count == 0
    await test()
    assert respx.calls.call_count == 0


def test_local_decorator_with_reference():
    router = respx.mock()

    @router
    def test(respx_mock):
        assert respx_mock is router

    test()


def test_local_decorator_without_reference():
    router = respx.mock()
    route = router.get("https://foo.bar/") % 202

    @router
    def test():
        assert respx.calls.call_count == 0
        response = httpx.get("https://foo.bar/")
        assert route.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 0
        assert router.calls.call_count == 1

    assert router.calls.call_count == 0
    assert respx.calls.call_count == 0
    test()
    assert respx.calls.call_count == 0


async def test_global_contextmanager(client):
    with respx.mock:
        assert respx.calls.call_count == 0
        request = respx.get("https://foo/bar/") % 202
        response = await client.get("https://foo/bar/")
        assert request.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 1

    async with respx.mock:
        assert respx.calls.call_count == 0
        request = respx.get("https://foo/bar/") % 202
        response = await client.get("https://foo/bar/")
        assert request.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 1

    assert respx.calls.call_count == 0


async def test_local_contextmanager(client):
    with respx.mock() as respx_mock:
        assert respx_mock.calls.call_count == 0
        request = respx_mock.get("https://foo/bar/") % 202
        response = await client.get("https://foo/bar/")
        assert request.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 0
        assert respx_mock.calls.call_count == 1

    async with respx.mock() as respx_mock:
        assert respx_mock.calls.call_count == 0
        request = respx_mock.get("https://foo/bar/") % 202
        response = await client.get("https://foo/bar/")
        assert request.called is True
        assert response.status_code == 202
        assert respx.calls.call_count == 0
        assert respx_mock.calls.call_count == 1

    assert respx.calls.call_count == 0


async def test_nested_local_contextmanager(client):
    with respx.mock() as respx_mock_1:
        get_request = respx_mock_1.get("https://foo/bar/") % 202

        with respx.mock() as respx_mock_2:
            post_request = respx_mock_2.post("https://foo/bar/") % 201
            assert len(respx_mock_1.routes) == 1
            assert len(respx_mock_2.routes) == 1

            response = await client.get("https://foo/bar/")
            assert get_request.called is True
            assert response.status_code == 202
            assert respx.calls.call_count == 0
            assert respx_mock_1.calls.call_count == 1
            assert respx_mock_2.calls.call_count == 0

            response = await client.post("https://foo/bar/")
            assert post_request.called is True
            assert response.status_code == 201
            assert respx.calls.call_count == 0
            assert respx_mock_1.calls.call_count == 1
            assert respx_mock_2.calls.call_count == 1

    assert len(respx.routes) == 0


async def test_nested_global_contextmanager(client):
    with respx.mock:
        get_request = respx.get("https://foo/bar/") % 202
        assert len(respx.routes) == 1

        with respx.mock:
            post_request = respx.post("https://foo/bar/") % 201
            assert len(respx.routes) == 2

            response = await client.get("https://foo/bar/")
            assert get_request.called is True
            assert response.status_code == 202
            assert respx.calls.call_count == 1

            response = await client.post("https://foo/bar/")
            assert post_request.called is True
            assert response.status_code == 201
            assert respx.calls.call_count == 2

        assert len(respx.routes) == 1

    assert len(respx.routes) == 0


async def test_configured_decorator(client):
    @respx.mock(assert_all_called=False, assert_all_mocked=False)
    async def test(respx_mock):
        assert respx_mock.calls.call_count == 0
        request = respx_mock.get("https://foo.bar/")
        response = await client.get("https://some.thing/")

        assert response.status_code == 200
        assert response.headers == httpx.Headers()
        assert response.text == ""

        assert request.called is False
        assert respx.calls.call_count == 0
        assert respx_mock.calls.call_count == 1

        _request, _response = respx_mock.calls.last
        assert _request is not None
        assert _response is not None
        assert respx_mock.calls.last.request is _request
        assert respx_mock.calls.last.response is _response
        assert _request.url == "https://some.thing/"

    await test()
    assert respx.calls.call_count == 0


@respx.mock(base_url="https://foo.bar")
async def test_configured_decorator_with_fixture(respx_mock, client):
    respx_mock.get("/")
    response = await client.get("https://foo.bar/")
    assert response.status_code == 200


async def test_configured_router_reuse(client):
    router = respx.mock()
    route = router.get("https://foo/bar/") % 404

    assert len(router.routes) == 1
    assert router.calls.call_count == 0

    with router:
        route.return_value = httpx.Response(202)
        response = await client.get("https://foo/bar/")
        assert route.called == True  # noqa: E712
        assert response.status_code == 202
        assert router.calls.call_count == 1
        assert respx.calls.call_count == 0

    assert len(router.routes) == 1
    assert route.called == False  # noqa: E712
    assert router.calls.call_count == 0

    async with router:
        assert router.calls.call_count == 0
        response = await client.get("https://foo/bar/")
        assert route.called == True  # noqa: E712
        assert response.status_code == 404
        assert router.calls.call_count == 1
        assert respx.calls.call_count == 0

    assert len(router.routes) == 1
    assert route.called == False  # noqa: E712
    assert router.calls.call_count == 0
    assert respx.calls.call_count == 0


async def test_router_return_type_misuse():
    router = respx.mock(assert_all_called=False)
    route = router.get("https://hot.dog/")

    with pytest.raises(TypeError):
        route.return_value = "not-a-httpx-response"  # type: ignore[assignment]


@respx.mock(base_url="https://ham.spam/")
async def test_nested_base_url(respx_mock):
    request = respx_mock.patch("/egg/") % dict(content="yolk")
    async with respx.mock(base_url="https://foo.bar/api/") as foobar_mock:
        request1 = foobar_mock.get("/baz/") % dict(content="baz")
        request2 = foobar_mock.post(path__regex=r"(?P<slug>\w+)/?$") % dict(text="slug")
        request3 = foobar_mock.route() % dict(content="ok")
        request4 = foobar_mock.patch("http://localhost/egg/") % 204

        async with httpx.AsyncClient(base_url="https://foo.bar/api") as client:
            response = await client.get("/baz/")
            assert request1.called is True
            assert response.text == "baz"

            response = await client.post("/apa/")
            assert request2.called is True
            assert response.text == "slug"

            response = await client.put("/")
            assert request3.called is True
            assert response.text == "ok"

            response = await client.patch("http://localhost/egg/")
            assert request4.called is True
            assert response.status_code == 204

            response = await client.patch("https://ham.spam/egg/")
            assert request.called is True
            assert response.text == "yolk"


def test_leakage(mocked_foo, mocked_ham):
    # NOTE: Including session fixtures, since they are pre-registered routers
    assert len(respx.routes) == 0
    assert len(respx.calls) == 0
    assert len(Mocker.registry["httpcore"].routers) == 2


async def test_start_stop(client):
    url = "https://start.stop/"
    request = respx.get(url) % 202

    try:
        respx.start()
        response = await client.get(url)
        assert request.called == True  # noqa: E712
        assert response.status_code == 202
        assert response.text == ""
        assert respx.calls.call_count == 1

        respx.stop(clear=False, reset=False)
        assert len(respx.routes) == 1
        assert respx.calls.call_count == 1
        assert request.called == True  # noqa: E712

        respx.reset()
        assert len(respx.routes) == 1
        assert respx.calls.call_count == 0
        assert request.called == False  # noqa: E712

        respx.clear()
        assert len(respx.routes) == 0

    finally:  # pragma: nocover
        respx.stop()  # Cleanup global state on error, to not affect other tests


@pytest.mark.parametrize(
    ("assert_all_called", "do_post", "raises"),
    [
        (
            True,
            False,
            pytest.raises(AssertionError, match="some routes were not called"),
        ),
        (True, True, does_not_raise()),
        (False, True, does_not_raise()),
        (False, False, does_not_raise()),
    ],
)
async def test_assert_all_called(client, assert_all_called, do_post, raises):
    with raises:
        async with MockRouter(assert_all_called=assert_all_called) as respx_mock:
            request1 = respx_mock.get("https://foo.bar/1/") % 404
            request2 = respx_mock.post("https://foo.bar/") % 201

            await client.get("https://foo.bar/1/")
            if do_post:
                await client.post("https://foo.bar/")

            assert request1.called is True
            assert request2.called is do_post


@pytest.mark.parametrize(
    ("assert_all_mocked", "raises"),
    [(True, pytest.raises(AllMockedAssertionError)), (False, does_not_raise())],
)
async def test_assert_all_mocked(client, assert_all_mocked, raises):
    with raises:
        with MockRouter(assert_all_mocked=assert_all_mocked) as respx_mock:
            response = httpx.get("https://foo.bar/")
            assert respx_mock.calls.call_count == 1
            assert response.status_code == 200
    with raises:
        async with MockRouter(assert_all_mocked=assert_all_mocked) as respx_mock:
            response = await client.get("https://foo.bar/")
            assert respx_mock.calls.call_count == 1
            assert response.status_code == 200
    assert respx_mock.calls.call_count == 0


def test_add_remove_targets():
    from respx.mocks import HTTPCoreMocker

    target = "httpcore._sync.connection.HTTPConnection"
    assert HTTPCoreMocker.targets.count(target) == 1
    HTTPCoreMocker.add_targets(target)
    assert HTTPCoreMocker.targets.count(target) == 1

    pre_add_count = len(HTTPCoreMocker.targets)
    try:
        HTTPCoreMocker.add_targets(
            "httpx._transports.asgi.ASGITransport",
            "httpx._transports.wsgi.WSGITransport",
        )
        assert len(HTTPCoreMocker.targets) == pre_add_count + 2

        HTTPCoreMocker.remove_targets("foobar")
        assert len(HTTPCoreMocker.targets) == pre_add_count + 2
    finally:
        HTTPCoreMocker.remove_targets(
            "httpx._transports.asgi.ASGITransport",
            "httpx._transports.wsgi.WSGITransport",
        )
        assert len(HTTPCoreMocker.targets) == pre_add_count


async def test_proxies():
    with respx.mock:
        respx.get("https://foo.bar/") % dict(json={"foo": "bar"})
        with httpx.Client(proxy="https://1.1.1.1:1") as client:
            response = client.get("https://foo.bar/")
        assert response.json() == {"foo": "bar"}

    async with respx.mock:
        respx.get("https://foo.bar/") % dict(json={"foo": "bar"})
        async with httpx.AsyncClient(proxy="https://1.1.1.1:1") as client:
            response = await client.get("https://foo.bar/")
        assert response.json() == {"foo": "bar"}


async def test_uds():
    async with respx.mock:
        uds = httpx.AsyncHTTPTransport(uds="/tmp/foobar.sock")
        async with httpx.AsyncClient(transport=uds) as client:
            request = respx.get("https://foo.bar/") % 202
            response = await client.get("https://foo.bar/")
            assert request.called is True
            assert response.status_code == 202


async def test_mock_using_none():
    @respx.mock(using=None)
    async def test(respx_mock):
        respx_mock.get("https://example.org/") % 204
        transport = httpx.MockTransport(respx_mock.handler)
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get("https://example.org/")
            assert response.status_code == 204

    await test()


async def test_router_using__none():
    router = respx.MockRouter(using=None)
    router.get("https://example.org/") % 204

    @router
    async def test():
        transport = httpx.MockTransport(router.handler)
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get("https://example.org/")
            assert response.status_code == 204

    await test()


def test_router_using__invalid():
    with pytest.raises(ValueError, match="using"):
        respx.MockRouter(using=123).using  # type: ignore[arg-type]


def test_mocker_subclass():
    with pytest.raises(TypeError, match="unique name"):

        class Foobar(Mocker):
            name = "httpcore"

    class Hamspam(Mocker):
        pass

    assert not hasattr(Hamspam, "routers")


def test_sync_httpx_mocker():
    class TestTransport(httpx.BaseTransport):
        def handle_request(self, *args, **kwargs):
            raise RuntimeError("would pass through")

    client = httpx.Client(transport=TestTransport())

    @respx.mock(using="httpx")
    def test(respx_mock):
        mock_route = respx_mock.get("https://example.org/") % 204
        pass_route = respx_mock.get(host="pass-through").pass_through()

        with client:
            response = client.get("https://example.org/")
            assert response.status_code == 204
            assert mock_route.call_count == 1

            with pytest.raises(RuntimeError, match="would pass through"):
                client.get("https://pass-through/")
            assert pass_route.call_count == 1

            with pytest.raises(AllMockedAssertionError):
                client.get("https://not-mocked/")

    with respx.mock(using="httpx"):  # extra registered router
        test()


async def test_async_httpx_mocker():
    class TestTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, *args, **kwargs):
            raise RuntimeError("would pass through")

    client = httpx.AsyncClient(transport=TestTransport())

    @respx.mock
    @respx.mock(using="httpx")
    async def test(respx_mock):
        respx.get(host="foo.bar")

        async def streaming_side_effect(request):
            async def content():
                yield b'{"foo"'
                yield b':"bar"}'

            return httpx.Response(204, content=content())

        mock_route = respx_mock.get("https://example.org/")
        mock_route.side_effect = streaming_side_effect
        pass_route = respx_mock.get(host="pass-through").pass_through()

        async with client:
            response = await client.get("https://example.org/")
            assert response.status_code == 204
            assert response.json() == {"foo": "bar"}
            assert mock_route.call_count == 1

            with pytest.raises(RuntimeError, match="would pass through"):
                await client.get("https://pass-through/")
            assert pass_route.call_count == 1

            with pytest.raises(AllMockedAssertionError):
                await client.get("https://not-mocked/")

    async with respx.mock(using="httpx"):  # extra registered router
        await test()


@pytest.mark.parametrize("using", ["httpcore", "httpx"])
async def test_async_side_effect(client, using):
    async def effect(request, slug):
        assert request.extensions.get("timeout", {}).get("read") == 44.0
        return httpx.Response(204, text=slug)

    async with respx.mock(using=using) as respx_mock:
        mock_route = respx_mock.get(
            "https://example.org/", path__regex=r"/(?P<slug>\w+)/"
        ).mock(side_effect=effect)
        response = await client.get("https://example.org/hello/", timeout=44.0)
        assert response.status_code == 204
        assert response.text == "hello"
        assert mock_route.called


@pytest.mark.parametrize("using", ["httpcore", "httpx"])
async def test_async_side_effect__exception(client, using):
    async def effect(request):
        raise httpx.ConnectTimeout("X-P", request=request)

    async with respx.mock(using=using) as respx_mock:
        mock_route = respx_mock.get("https://example.org/").mock(side_effect=effect)
        with pytest.raises(httpx.ConnectTimeout):
            await client.get("https://example.org/")
        assert mock_route.called


@pytest.mark.parametrize("using", ["httpcore", "httpx"])
async def test_async_app_route(client, using):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def baz(request):
        return JSONResponse({"ham": "spam"})

    app = Starlette(routes=[Route("/baz/", baz)])

    async with respx.mock(using=using, base_url="https://foo.bar/") as respx_mock:
        app_route = respx_mock.route().mock(side_effect=ASGIHandler(app))
        response = await client.get("https://foo.bar/baz/")
        assert response.json() == {"ham": "spam"}
        assert app_route.called

    async with respx.mock:
        respx.route(host="foo.bar").mock(side_effect=ASGIHandler(app))
        response = await client.get("https://foo.bar/baz/")
        assert response.json() == {"ham": "spam"}


@pytest.mark.parametrize("using", ["httpcore", "httpx"])
def test_sync_app_route(using):
    from flask import Flask

    app = Flask("foobar")

    @app.route("/baz/")
    def baz():
        return {"ham": "spam"}

    with respx.mock(using=using, base_url="https://foo.bar/") as respx_mock:
        app_route = respx_mock.route().mock(side_effect=WSGIHandler(app))
        response = httpx.get("https://foo.bar/baz/")
        assert response.json() == {"ham": "spam"}
        assert app_route.called

    with respx.mock:
        respx.route(host="foo.bar").mock(side_effect=WSGIHandler(app))
        response = httpx.get("https://foo.bar/baz/")
        assert response.json() == {"ham": "spam"}


@pytest.mark.parametrize(
    ("url", "port"),
    [
        ("https://foo.bar/", None),
        ("https://foo.bar:443/", 443),
    ],
)
async def test_httpcore_request(url, port):
    async with MockRouter(using="httpcore") as router:
        router.get(url) % dict(text="foobar")

        request = httpcore.Request(
            b"GET",
            httpcore.URL(scheme=b"https", host=b"foo.bar", port=port, target=b"/"),
        )

        with httpcore.ConnectionPool() as http:
            response = http.handle_request(request)
            body = response.read()
            assert body == b"foobar"

        async with httpcore.AsyncConnectionPool() as http:
            response = await http.handle_async_request(request)
            body = await response.aread()
            assert body == b"foobar"


async def test_route_rollback():
    respx_mock = respx.mock()

    def example(request, route):
        route.mock(return_value=httpx.Response(404))
        return httpx.Response(202)

    route = respx_mock.delete("https://example.org/foobar/")
    route.side_effect = example

    with respx_mock:
        async with httpx.AsyncClient(base_url="https://example.org/") as client:
            response = await client.delete("/foobar/")
            assert response.status_code == 202

            response = await client.delete("/foobar/")
            assert response.status_code == 404

    with respx_mock:
        async with httpx.AsyncClient(base_url="https://example.org/") as client:
            response = await client.delete("/foobar/")
            assert response.status_code == 202
