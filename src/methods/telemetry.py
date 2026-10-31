from contextlib import nullcontext
from functools import wraps
from importlib import import_module
import os

from .config import get_config

_client = None


def backend():
    global _client
    if not get_config()["weave"]["enabled"]:
        return None
    if _client is None:
        project = os.getenv("PROJECT_NAME")
        if not project:
            raise ValueError("PROJECT_NAME is required when Weave logging is enabled")
        weave = import_module("weave")

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
