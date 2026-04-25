"""
Map legacy openai.ChatCompletion.create (SDK 0.28) onto OpenAI SDK 1.x client.

Call openai_chat_compat.install() after import openai and any openai.api_key assignment.
Safe to call twice; no-ops on openai package version < 1.
"""
from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version


def _openai_major() -> int | None:
    try:
        return int(version("openai").split(".")[0])
    except (PackageNotFoundError, ValueError):
        return None


class _AttrMap(dict):
    """dict that also allows r.choices / r.choices[0].message so legacy and resp['choices'] both work."""

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value) -> None:  # pragma: no cover
        self[name] = value


def _legacy_chat_response_from_completion(completion) -> _AttrMap:
    msg = completion.choices[0].message
    content = (msg.content or "") if msg else ""
    return _AttrMap(choices=[_AttrMap(message=_AttrMap([("content", content)]))])


def install() -> None:
    import openai

    if getattr(openai, "_pinterest_chat_compat_installed", False):
        return

    maj = _openai_major()
    if maj is not None and maj < 1:
        return

    try:
        from openai import OpenAI
    except ImportError:
        return

    def _create_chat(*args, **kwargs):
        kwargs = dict(kwargs)
        if "request_timeout" in kwargs:
            kwargs["timeout"] = kwargs.pop("request_timeout")
        api_key = kwargs.pop("api_key", None) or getattr(openai, "api_key", None) or os.environ.get(
            "OPENAI_API_KEY"
        )
        client = OpenAI(api_key=api_key)
        # v1 Completions.create is keyword-only; never forward a stray "self" from a broken descriptor bind.
        if args:
            raise TypeError(
                "ChatCompletion.create does not take positional args; use model=, messages=, ... only."
            )
        completion = client.chat.completions.create(**kwargs)
        return _legacy_chat_response_from_completion(completion)

    class _ChatCompletionNS:
        # Must be staticmethod: assigning a nested @staticmethod to another class can re-bind as instance method.
        create = staticmethod(_create_chat)

    openai.ChatCompletion = _ChatCompletionNS()
    openai._pinterest_chat_compat_installed = True
