"""Regression tests: numbered LLM responses must map back to regions by index.

The old parsers split responses on '<|N|>' markers and assumed the response
order equals the request order. When the LLM reorders, drops or duplicates
items (common under upstream errors/retries), the translations silently
shifted between text regions (翻译错位). These tests pin the index-based
mapping introduced to fix that.
"""

import asyncio

import pytest

from manga_translator.translators.common_gpt import parse_indexed_translations
from manga_translator.translators.custom_openai import CustomOpenAiTranslator
from manga_translator.translators.deepseek import DeepseekTranslator


QUERIES = ["あの…", "きみは誰？", "ここどこ？", "助けて！"]
ORDERED = ["那个…", "你是谁？", "这里是哪里？", "救命！"]


def test_parse_indexed_in_order():
    resp = "<|1|>那个…\n<|2|>你是谁？\n<|3|>这里是哪里？\n<|4|>救命！"
    assert parse_indexed_translations(resp, 4) == ORDERED


def test_parse_indexed_reordered():
    resp = "<|4|>救命！\n<|2|>你是谁？\n<|1|>那个…\n<|3|>这里是哪里？"
    assert parse_indexed_translations(resp, 4) == ORDERED


def test_parse_indexed_with_preamble_and_continuation():
    resp = (
        "好的，以下是翻译：\n"
        "<|3|>这里是\n哪里？\n"
        "<|1|>那个…\n"
        "<|4|>救命！\n"
        "<|2|>你\n是谁？"
    )
    assert parse_indexed_translations(resp, 4) == ORDERED


@pytest.mark.parametrize(
    "resp",
    [
        "<|1|>那个…\n<|3|>这里是哪里？",  # missing indices
        "<|1|>那个…\n<|2|>你是谁？\n<|2|>你是谁？\n<|3|>这里是哪里？\n<|4|>救命！",  # duplicate
        "<|0|>那个…\n<|2|>你是谁？\n<|3|>这里是哪里？\n<|4|>救命！",  # out of range
        "<|1|>那个…\n<|2|>\n<|3|>这里是哪里？\n<|4|>救命！",  # empty item
    ],
)
def test_parse_indexed_malformed(resp):
    assert parse_indexed_translations(resp, 4) is None


@pytest.mark.asyncio
async def test_custom_openai_reordered_response():
    translator = CustomOpenAiTranslator(check_openai_key=False)
    responses = iter(
        [
            "<|4|>救命！\n<|2|>你是谁？\n<|1|>那个…\n<|3|>这里是哪里？",
        ]
    )

    async def fake_request(to_lang: str, prompt: str) -> str:
        return next(responses)

    translator._request_translation = fake_request
    result = await translator._translate("JPN", "CHS", QUERIES)
    assert result == ORDERED


@pytest.mark.asyncio
async def test_custom_openai_malformed_then_ok_retries():
    translator = CustomOpenAiTranslator(check_openai_key=False)
    responses = iter(
        [
            "<|1|>那个…\n<|3|>这里是哪里？",  # malformed (missing items)
            "<|4|>救命！\n<|2|>你是谁？\n<|1|>那个…\n<|3|>这里是哪里？",  # reordered but complete
        ]
    )

    async def fake_request(to_lang: str, prompt: str) -> str:
        return next(responses)

    translator._request_translation = fake_request
    result = await translator._translate("JPN", "CHS", QUERIES)
    assert result == ORDERED


@pytest.mark.asyncio
async def test_custom_openai_persistent_malformed_raises():
    translator = CustomOpenAiTranslator(check_openai_key=False)

    async def fake_request(to_lang: str, prompt: str) -> str:
        return "<|1|>那个…\n<|3|>这里是哪里？"  # always malformed

    translator._request_translation = fake_request
    with pytest.raises(Exception, match="malformed numbered response"):
        await translator._translate("JPN", "CHS", QUERIES)


@pytest.mark.asyncio
async def test_deepseek_reordered_response():
    translator = DeepseekTranslator(check_openai_key=False)
    responses = iter(
        [
            "<|4|>救命！\n<|2|>你是谁？\n<|1|>那个…\n<|3|>这里是哪里？",
        ]
    )

    async def fake_request(to_lang: str, prompt: str) -> str:
        return next(responses)

    translator._request_translation = fake_request
    result = await translator._translate("JPN", "CHS", QUERIES)
    assert result == ORDERED


@pytest.mark.asyncio
async def test_deepseek_single_query_without_marker():
    translator = DeepseekTranslator(check_openai_key=False)

    async def fake_request(to_lang: str, prompt: str) -> str:
        return "你是谁？"  # single query: LLM often omits <|1|>

    translator._request_translation = fake_request
    result = await translator._translate("JPN", "CHS", ["きみは誰？"])
    assert result == ["你是谁？"]


@pytest.mark.asyncio
async def test_deepseek_malformed_then_ok_retries():
    translator = DeepseekTranslator(check_openai_key=False)
    responses = iter(
        [
            "<|1|>那个…\n<|3|>这里是哪里？",  # malformed
            "<|4|>救命！\n<|2|>你是谁？\n<|1|>那个…\n<|3|>这里是哪里？",  # reordered but complete
        ]
    )

    async def fake_request(to_lang: str, prompt: str) -> str:
        return next(responses)

    translator._request_translation = fake_request
    result = await translator._translate("JPN", "CHS", QUERIES)
    assert result == ORDERED
