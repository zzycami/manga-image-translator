import re

from ..config import TranslatorConfig
from .config_gpt import ConfigGPT  # Import the `gpt_config` parsing parent class
from .common_gpt import normalize_index_markers, parse_indexed_translations

try:
    import openai
except ImportError:
    openai = None
import asyncio
import time
from typing import List
from .common import CommonTranslator, VALID_LANGUAGES, resolve_llm_language_pair
from .keys import CUSTOM_OPENAI_API_KEY, CUSTOM_OPENAI_API_BASE, CUSTOM_OPENAI_MODEL, CUSTOM_OPENAI_MODEL_CONF


class CustomOpenAiTranslator(ConfigGPT, CommonTranslator):
    _INVALID_REPEAT_COUNT = 2  # 如果检测到"无效"翻译，最多重复 2 次
    _MAX_REQUESTS_PER_MINUTE = 40  # 每分钟最大请求次数
    _TIMEOUT = 40  # 在重试之前等待服务器响应的时间（秒）
    _RETRY_ATTEMPTS = 3  # 在放弃之前重试错误请求的次数
    _TIMEOUT_RETRY_ATTEMPTS = 3  # 在放弃之前重试超时请求的次数
    _RATELIMIT_RETRY_ATTEMPTS = 3  # 在放弃之前重试速率限制请求的次数
    _PARSE_RETRY_ATTEMPTS = 3  # 编号响应无法按索引归位时、拆分前的重试次数
    _MAX_SPLIT_ATTEMPTS = 5  # 解析仍失败时对半拆批的最大层数（与 Deepseek/ChatGPT 一致）

    # 最大令牌数量，用于控制处理的文本长度
    _MAX_TOKENS = 4096

    # 是否返回原始提示，用于控制输出内容
    _RETURN_PROMPT = False

    # 是否包含模板，用于决定是否使用预设的提示模板
    _INCLUDE_TEMPLATE = False

    def __init__(self, model=None, api_base=None, api_key=None, check_openai_key=False):
        # If the user has specified a nested key to use for the model, append the key
        #   Otherwise: Use the `ollama` defaults.
        _CONFIG_KEY='ollama'
        if CUSTOM_OPENAI_MODEL_CONF:
            _CONFIG_KEY+=f".{CUSTOM_OPENAI_MODEL_CONF}"

        ConfigGPT.__init__(self, config_key=_CONFIG_KEY)
        self.model = model
        CommonTranslator.__init__(self)
        self.client = openai.AsyncOpenAI(api_key=api_key or CUSTOM_OPENAI_API_KEY or "ollama") # required, but unused for ollama
        self.client.base_url = api_base or CUSTOM_OPENAI_API_BASE
        self.token_count = 0
        self.token_count_last = 0

    def parse_args(self, args: TranslatorConfig):
        self.config = args.chatgpt_config

    def parse_language_codes(self, from_lang: str, to_lang: str, fatal: bool = False):
        return resolve_llm_language_pair(self, from_lang, to_lang, fatal=fatal)

    @property
    def chat_system_template(self) -> str:
        return self._config_get('chat_system_template', self._CHAT_SYSTEM_TEMPLATE_CONCISE)

    @property
    def temperature(self) -> float:
        # Volcengine ARK: lower default than generic GPT translators to reduce target-lang drift.
        return self._config_get('temperature', 0.2)


    def extract_capture_groups(self, text, regex=r"(.*)"):
        """
        Extracts all capture groups from matches and concatenates them into a single string.
        
        :param text: The multi-line text to search.
        :param regex: The regex pattern with capture groups.
        :return: A concatenated string of all matched groups.
        """
        pattern = re.compile(regex, re.DOTALL)  # DOTALL to match across multiple lines
        matches = pattern.findall(text)  # Find all matches
        
        # Ensure matches are concatonated (handles multiple groups per match)
        extracted_text = "\n".join(
            "\n".join(m) if isinstance(m, tuple) else m for m in matches
        )
        
        return extracted_text.strip() if extracted_text else None

    def _assemble_prompts(self, from_lang: str, to_lang: str, queries: List[str]):
        prompt = ''

        if self._INCLUDE_TEMPLATE:
            prompt += self.prompt_template.format(to_lang=to_lang)

        if self._RETURN_PROMPT:
            prompt += '\nOriginal:'

        i_offset = 0
        for i, query in enumerate(queries):
            prompt += f'\n<|{i + 1 - i_offset}|>{query}'

            # If prompt is growing too large and there's still a lot of text left
            # split off the rest of the queries into new prompts.
            # 1 token = ~4 characters according to https://platform.openai.com/tokenizer
            # TODO: potentially add summarizations from special requests as context information
            if self._MAX_TOKENS * 2 and len(''.join(queries[i + 1:])) > self._MAX_TOKENS:
                if self._RETURN_PROMPT:
                    prompt += '\n<|1|>'
                yield prompt.lstrip(), i + 1 - i_offset
                prompt = self.prompt_template.format(to_lang=to_lang)
                # Restart counting at 1
                i_offset = i + 1

        if self._RETURN_PROMPT:
            prompt += '\n<|1|>'

        yield prompt.lstrip(), len(queries) - i_offset

    def _format_prompt_log(self, to_lang: str, prompt: str) -> str:
        if to_lang in self.chat_sample:
            return '\n'.join([
                'System:',
                self.chat_system_template.format(to_lang=to_lang),
                'User:',
                self.chat_sample[to_lang][0],
                'Assistant:',
                self.chat_sample[to_lang][1],
                'User:',
                prompt,
            ])
        else:
            return '\n'.join([
                'System:',
                self.chat_system_template.format(to_lang=to_lang),
                'User:',
                prompt,
            ])

    def _parse_translations(self, response: str, query_size: int) -> List[str] | None:
        """Parse a numbered response into request order (by <|N|> index)."""
        response = self.extract_capture_groups(response, rf"{self.rgx_capture}") or response
        response = normalize_index_markers(response)
        parsed = parse_indexed_translations(response, query_size)
        if parsed is not None:
            return parsed
        # When there is only one query LLMs like to exclude the <|1|> entirely.
        if query_size == 1 and response.strip() and not re.search(r'<\|\d+\|>', response):
            return [response.strip()]
        return None

    @staticmethod
    def _parse_retry_suffix(query_size: int) -> str:
        """Nudge the model after a malformed numbered reply (common: merging lines)."""
        return (
            f'\n\nIMPORTANT: Your previous reply was invalid. '
            f'Output exactly {query_size} lines with prefixes '
            f'<|1|> through <|{query_size}|>. '
            f'Do not merge lines. Do not skip or renumber items.'
        )

    async def _translate(self, from_lang: str, to_lang: str, queries: List[str]) -> List[str]:
        """Translate with parse retries, then split the batch like Deepseek/ChatGPT.

        Strict index parsing prevents silent region misalignment; when the model
        keeps merging OCR-split lines (e.g. expected 6, got 5), splitting the
        batch usually recovers instead of failing the whole page.
        """
        translations = [''] * len(queries)
        self.logger.debug(f'Temperature: {self.temperature}, TopP: {self.top_p}')

        async def translate_batch(
            prompt_queries: List[str],
            prompt_query_indices: List[int],
            split_level: int = 0,
        ) -> bool:
            split_prefix = ' (split)' if split_level > 0 else ''
            prompt, query_size = next(self._assemble_prompts(from_lang, to_lang, prompt_queries))
            self.logger.debug(
                f'-- GPT Prompt{split_prefix} --\n' + self._format_prompt_log(to_lang, prompt)
            )

            for attempt in range(self._PARSE_RETRY_ATTEMPTS):
                request_prompt = prompt
                request_temperature = self.temperature
                if attempt > 0:
                    request_prompt = prompt + self._parse_retry_suffix(query_size)
                    # Slightly raise temperature so retries are less likely to
                    # repeat the same merge/skip pattern.
                    request_temperature = min(self.temperature + 0.15 * attempt, 0.7)

                ratelimit_attempt = 0
                server_error_attempt = 0
                timeout_attempt = 0
                while True:
                    request_task = asyncio.create_task(
                        self._request_translation(
                            to_lang,
                            request_prompt,
                            temperature=request_temperature,
                        )
                    )
                    started = time.time()
                    while not request_task.done():
                        await asyncio.sleep(0.1)
                        if time.time() - started > self._TIMEOUT + (
                            timeout_attempt * self._TIMEOUT / 2
                        ):
                            if timeout_attempt >= self._TIMEOUT_RETRY_ATTEMPTS:
                                raise Exception('ollama servers did not respond quickly enough.')
                            timeout_attempt += 1
                            self.logger.warning(
                                f'Restarting request due to timeout. Attempt: {timeout_attempt}'
                            )
                            request_task.cancel()
                            request_task = asyncio.create_task(
                                self._request_translation(
                                    to_lang,
                                    request_prompt,
                                    temperature=request_temperature,
                                )
                            )
                            started = time.time()
                    try:
                        response = await request_task
                        break
                    except openai.RateLimitError:
                        ratelimit_attempt += 1
                        if ratelimit_attempt >= self._RATELIMIT_RETRY_ATTEMPTS:
                            raise
                        self.logger.warning(
                            'Restarting request due to ratelimiting by Ollama servers. '
                            f'Attempt: {ratelimit_attempt}'
                        )
                        await asyncio.sleep(2)
                    except openai.APIError:
                        server_error_attempt += 1
                        if server_error_attempt >= self._RETRY_ATTEMPTS:
                            self.logger.error(
                                'Ollama encountered a server error, possibly due to high '
                                'server load. Use a different translator or try again later.'
                            )
                            raise
                        self.logger.warning(
                            f'Restarting request due to a server error. '
                            f'Attempt: {server_error_attempt}'
                        )
                        await asyncio.sleep(1)

                parsed = self._parse_translations(response, query_size)
                if parsed is not None:
                    for idx, translation in zip(prompt_query_indices, parsed):
                        translations[idx] = translation
                    self.logger.info(
                        f'Batch translated{split_prefix}: '
                        f'{len([t for t in translations if t])}/{len(queries)} completed.'
                    )
                    return True

                remaining = self._PARSE_RETRY_ATTEMPTS - attempt - 1
                self.logger.warning(
                    f'Malformed numbered response (expected {query_size} items), '
                    f'remaining {remaining} time(s) before splitting the batch.'
                )

            if len(prompt_queries) > 1 and split_level < self._MAX_SPLIT_ATTEMPTS:
                if split_level == 0:
                    self.logger.warning(
                        'Retry limit reached. Splitting the translation batch.'
                    )
                else:
                    self.logger.warning(
                        'Further splitting the translation batch due to persistent errors.'
                    )
                mid = len(prompt_queries) // 2
                futures = []
                for sub_queries, sub_indices in (
                    (prompt_queries[:mid], prompt_query_indices[:mid]),
                    (prompt_queries[mid:], prompt_query_indices[mid:]),
                ):
                    if sub_queries:
                        futures.append(
                            translate_batch(sub_queries, sub_indices, split_level + 1)
                        )
                results = await asyncio.gather(*futures)
                return all(results)

            self.logger.error(
                'Unable to parse numbered translations after retries/splits for queries: '
                + ' | '.join(prompt_queries)
            )
            return False

        ok = await translate_batch(queries, list(range(len(queries))))
        if not ok or any(not (t or '').strip() for t in translations):
            raise Exception(
                'Translator returned a malformed numbered response '
                f'(expected {len(queries)} items) after retries and splits'
            )

        for t in translations:
            if "I'm sorry, but I can't assist with that request" in t:
                raise Exception('translations contain error text')
        self.logger.debug(translations)
        if self.token_count_last:
            self.logger.info(f'Used {self.token_count_last} tokens (Total: {self.token_count})')

        return translations

    async def _request_translation(
        self,
        to_lang: str,
        prompt: str,
        temperature: float | None = None,
    ) -> str:
        messages = [{'role': 'system', 'content': self.chat_system_template.format(to_lang=to_lang)}]

        few_shot_lang = getattr(self, '_few_shot_to_lang', to_lang)
        lang_chat_samples = self.get_chat_sample(few_shot_lang)
        if lang_chat_samples:
            messages.append({'role': 'user', 'content': lang_chat_samples[0]})
            messages.append({'role': 'assistant', 'content': lang_chat_samples[1]})

        messages.append({'role': 'user', 'content': prompt})

        response = await self.client.chat.completions.create(
            model=self.model or CUSTOM_OPENAI_MODEL,
            messages=messages,
            max_tokens=self._MAX_TOKENS // 2,
            temperature=self.temperature if temperature is None else temperature,
            top_p=self.top_p,
        )

        self.logger.debug('\n-- GPT Response (raw) --')
        self.logger.debug(response.choices[0].message.content)
        self.logger.debug('------------------------\n')


        self.token_count += response.usage.total_tokens
        self.token_count_last = response.usage.total_tokens

        return response.choices[0].message.content
