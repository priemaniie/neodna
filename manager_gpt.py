import random
import g4f
import g4f.debug
import httpx
from g4f.client import Client
from g4f.Provider import FreeChatgpt, Liaobots, Phind, RetryProvider
from openai import OpenAI

from config import settings

g4f.debug.logging = settings.gpt_debug


class GptClient:
    def __init__(self, role: str, proxy: str = None) -> None:
        if settings.gpt_api_key_use:
            custom_http_client = httpx.Client(proxy=f"http://{settings.gpt_proxy}")
            self.client = OpenAI(
                api_key=settings.gpt_api_key,
                http_client=custom_http_client,
            )
        else:
            self.client = Client(
                proxies=f"http://{proxy}" if proxy else proxy,
                provider=RetryProvider([Phind, FreeChatgpt, Liaobots], shuffle=False),
            )
        self.role = role

    def get_context_comment_by_language(
        self, post: str, language: str, max_symbol_limit: int = 250
    ):
        # Optional: Include random topics and tones in comments
        random_topic = random.choice(settings.topics)
        random_tone = random.choice(settings.tones)
        response = self.client.chat.completions.create(
            model=settings.gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": settings.gpt_template_comment_by_language_system_role.format(
                        role=self.role,
                        language=language,
                        max_symbol_limit=max_symbol_limit,
                        random_topic=random_topic,
                        random_tone=random_tone,
                    ),
                },
                {
                    "role": "user",
                    "content": settings.gpt_template_comment_by_language_user_role.format(
                        post=post,
                        role=self.role,
                        language=language,
                        max_symbol_limit=max_symbol_limit,
                        random_topic=random_topic,
                        random_tone=random_tone,
                    ),
                },
            ],
            temperature=settings.gpt_temperature,
            stop=settings.gpt_stop_words,
        )
        return response.choices[0].message.content

    def get_context_comment(self, post: str, max_symbol_limit: int = 250):
        # Optional: Include random topics and tones in comments
        random_topic = random.choice(settings.topics)
        random_tone = random.choice(settings.tones)
        response = self.client.chat.completions.create(
            model=settings.gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": settings.gpt_template_comment_context_system_role.format(
                        role=self.role,
                        max_symbol_limit=max_symbol_limit,
                        random_topic=random_topic,
                        random_tone=random_tone,
                    ),
                },
                {
                    "role": "user",
                    "content": settings.gpt_template_comment_context_user_role.format(
                        post=post,
                        role=self.role,
                        max_symbol_limit=max_symbol_limit,
                        random_topic=random_topic,
                        random_tone=random_tone,
                    ),
                },
            ],
            temperature=settings.gpt_temperature,
            stop=settings.gpt_stop_words,
        )
        return response.choices[0].message.content

    def get_post(self, language: str, max_symbol_limit: int = 250):
        # Import random module
        random_topic = random.choice(settings.topics)
        random_tone = random.choice(settings.tones)
        response = self.client.chat.completions.create(
            model=settings.gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": settings.gpt_template_post_system_role.format(
                        role=self.role
                    ),
                },
                {
                    "role": "user",
                    "content": settings.gpt_template_post_user_role.format(
                        role=self.role,
                        language=language,
                        max_symbol_limit=max_symbol_limit,
                        random_topic=random_topic,
                        random_tone=random_tone,
                    ),
                },
            ],
            temperature=settings.gpt_temperature,
            stop=settings.gpt_stop_words,
        )
        return response.choices[0].message.content

    def get_msg(self, content: str):
        response = self.client.chat.completions.create(
            model=settings.gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": self.role,
                },
                {
                    "role": "user",
                    "content": content,
                },
            ],
            temperature=settings.gpt_temperature,
            stop=settings.gpt_stop_words,
        )
        return response.choices[0].message.content
