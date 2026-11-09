from contextlib import nullcontext
from functools import wraps
from importlib import import_module
import os

from .config import get_config

_client = None


def reuse_cached_wandb_login():
    if os.getenv("WANDB_API_KEY"):
        return
    try:
        setup = import_module("wandb.sdk.wandb_setup")
        settings = setup.singleton().settings
        credential = settings.api_key
        if not credential:
            auth = import_module("wandb.sdk.lib.wbauth")
            credential = auth.read_netrc_auth(host=settings.base_url)
    except ImportError:
        # Older W&B versions use the credential lookup bundled with Weave.
        return
    if credential:
        os.environ["WANDB_API_KEY"] = credential


def align_weave_auth_transport():
    try:
        api = import_module("weave.compat.wandb.wandb_thin.internal_api")
        transport = import_module("gql.transport.httpx")
    except ImportError:
        return
    if getattr(api, "httpx", None) is not None and getattr(transport, "httpx", None):
        # gql may use httpx2 while Weave's bundled client imports httpx.
        # Match BasicAuth to that transport without changing either global library.
        api.httpx = transport.httpx  # type: ignore


def backend():
    global _client
    if not get_config()["weave"]["enabled"]:
        return None
    if _client is None:
        project = os.getenv("PROJECT_NAME")
        if not project:
            raise ValueError("PROJECT_NAME is required when Weave logging is enabled")
        weave = import_module("weave")

        reuse_cached_wandb_login()
        align_weave_auth_transport()
        weave.init(project)
        _client = weave
    return _client


def op(function):
    traced = None

    @wraps(function)
    def wrapped(*args, **kwargs):
        nonlocal traced
        client = backend()
        if client is None:
            kwargs.pop("__weave", None)
            return function(*args, **kwargs)
        if traced is None:
            traced = client.op(function)
        return traced(*args, **kwargs)

    return wrapped


def thread(**kwargs):
    client = backend()
    return client.thread(**kwargs) if client else nullcontext()


def attributes(values):
    client = backend()
    return client.attributes(values) if client else nullcontext()


def evaluation_logger(**kwargs):
    client = backend()
    return client.EvaluationLogger(**kwargs) if client else None
