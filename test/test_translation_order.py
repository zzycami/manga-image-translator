"""Regression tests: numbered LLM responses must map back to regions by index.

The old parsers split responses on '<|N|>' markers and assumed the response
order equals the request order. When the LLM reorders, drops or duplicates
items (common under upstream errors/retries), the translations silently
shifted between text regions (翻译错位). These tests pin the index-based
mapping introduced to fix that.
"""

import asyncio
import re

import pytest

from manga_translator.translators.common_gpt import normalize_index_markers, parse_indexed_translations
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


def test_parse_indexed_extra_pipe_in_marker():
    # Volcengine ARK occasionally emits <|3||> instead of <|3|>.
    resp = "<|1|>那个…\n<|2|>你是谁？\n<|3||>这里是哪里？\n<|4|>救命！"
    assert parse_indexed_translations(resp, 4) == ORDERED
    assert normalize_index_markers("<|3||>x") == "<|3|>x"


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

    async def fake_request(to_lang: str, prompt: str, temperature: float | None = None) -> str:
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

    async def fake_request(to_lang: str, prompt: str, temperature: float | None = None) -> str:
        return next(responses)

    translator._request_translation = fake_request
    result = await translator._translate("JPN", "CHS", QUERIES)
    assert result == ORDERED


@pytest.mark.asyncio
async def test_custom_openai_persistent_malformed_raises():
    translator = CustomOpenAiTranslator(check_openai_key=False)

    async def fake_request(to_lang: str, prompt: str, temperature: float | None = None) -> str:
        return "<|1|>那个…\n<|3|>这里是哪里？"  # always malformed (even after splits)

    translator._request_translation = fake_request
    with pytest.raises(Exception, match="malformed numbered response"):
        await translator._translate("JPN", "CHS", QUERIES)


@pytest.mark.asyncio
async def test_custom_openai_split_recovers_when_full_batch_merges():
    """Mirrors production failure: model merges OCR-split lines on the full batch.

    After parse retries, the batch is split; smaller batches return complete
    numbered replies and the page succeeds instead of failing outright.
    """
    translator = CustomOpenAiTranslator(check_openai_key=False)
    # Keep parse retries low so the test reaches split quickly.
    translator._PARSE_RETRY_ATTEMPTS = 2

    async def fake_request(to_lang: str, prompt: str, temperature: float | None = None) -> str:
        body = prompt.split("IMPORTANT:")[0]
        n = len(re.findall(r"<\|(\d+)\|>", body))
        if n >= 4:
            # Same class of bug as task 975433: drop/merge so count is short.
            return "<|1|>那个…\n<|2|>你是谁？\n<|3|>这里是哪里？"
        if n == 2:
            # Reconstruct from the two source lines in the prompt.
            src = re.findall(r"<\|(\d+)\|>(.*)", body)
            out = []
            for idx, text in src:
                # Map known fixtures; fall back to echoing for robustness.
                mapping = dict(zip(QUERIES, ORDERED))
                out.append(f"<|{idx}|>{mapping.get(text.strip(), text.strip())}")
            return "\n".join(out)
        if n == 1:
            m = re.search(r"<\|1\|>(.*)", body)
            src = (m.group(1).strip() if m else "").split("\n")[0]
            mapping = dict(zip(QUERIES, ORDERED))
            return f"<|1|>{mapping.get(src, src)}"
        return "<|1|>?"

    translator._request_translation = fake_request
    result = await translator._translate("JPN", "CHS", QUERIES)
    assert result == ORDERED


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
