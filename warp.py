import json
import math
import os
import random
import shutil
import time
from datetime import datetime
from typing import List, Optional, Union

import pytz
import requests
from loguru import logger
from tqdm import tqdm

from config import settings
from manager_gpt import GptClient
from models import Account
from warpcast_modified import WarpModified


class Warp:
    def __init__(self, account: Account, text: Optional[str] = None) -> None:
        self.client = WarpModified(mnemonic=account.ps, proxy=account.proxy)
        self.client_gpt = GptClient(role=account.role)
        self.language = account.language
        self.post_max_symbol_limit = account.post_max_symbol_limit
        self.text = text
        self.me = self.client.me
        self.splayer_api_url = "https://basebuy.website"

    def get_users(self, total_limit=300):
        logger.info(
            f"@{self.me.username}: Старт, получение пользователей для взаймодействий. От 10 секунд до 1 минуты при дефолтных настройках кол-ва."
        )

        users = []
        donor_names = settings.donar_names
        num_donors = len(donor_names)
        limit_per_donor = total_limit // num_donors

        self.client.update_contact_device_state()
        time.sleep(1)

        pbar = tqdm(
            total=total_limit,
            desc="Собираем пользователей для работы софта",
            unit="user",
        )

        for donor_name in donor_names:
            fid = self.client.get_user_by_username(username=donor_name).fid
            cursor = None
            donor_users = []

            self.client.send_device()

            while len(donor_users) < limit_per_donor:
                response = self.client.get_followers(fid=fid, cursor=cursor, limit=100)
                for user in response.users:
                    base_conditions = [
                        int(user.fid) != int(self.me.fid),
                        user.follower_count > settings.min_followers_per_user,
                    ]
                    pfp_conditions = (
                        hasattr(user, "pfp")
                        and user.pfp
                        and user.pfp.url
                        != "https://imagedelivery.net/BXluQx4ige9GuW0Ia56BHw/3ffc18c3-e259-432c-8d42-5f07e140be00/rectcrop3"
                    )
                    base_conditions.append(pfp_conditions)
                    if settings.power_badge:
                        base_conditions.append(user.active_on_fc_network is True)
                    if all(base_conditions):
                        donor_users.append(user)
                        pbar.update(1)

                        if len(donor_users) >= limit_per_donor:
                            break

                cursor = response.cursor

                if response.cursor is None or len(donor_users) >= limit_per_donor:
                    break

                time.sleep(1)

            users.extend(donor_users)

            if len(users) >= total_limit:
                break

        pbar.close()
        logger.info(
            f"@{self.me.username}: Успешно собрали пользователей для взаймодействий."
        )

        return users[:total_limit]

    def timestamp_convert(self, ts: int):
        timestamp_seconds = ts / 1000
        dt = datetime.fromtimestamp(timestamp_seconds, tz=pytz.UTC)
        dt_moscow = dt.astimezone(pytz.timezone("Europe/Moscow"))
        return dt_moscow.strftime("%d %B %Y %H:%M:%S")

    def move_img(self, img_name: str):
        source_path = os.path.join(settings.default_img_path, img_name)
        if not os.path.exists(settings.use_img_path):
            os.makedirs(settings.use_img_path)
        destination_path = os.path.join(settings.use_img_path, img_name)
        shutil.move(source_path, destination_path)

    def get_random_img(self):
        all_files = os.listdir("data/const/img/")
        image_list = [
            f
            for f in all_files
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"))
        ]
        if not image_list:
            logger.error("Набор картинок закончился!")
            return None

        if random.random() < (settings.probability / 100):
            random_img_name = random.choice(image_list)
            logger.info(f"Делаем действие с картинкой {random_img_name}")
            uploaded_img_url = self.client.upload_img(
                file_path=settings.default_img_path + "/" + random_img_name
            )
            self.move_img(img_name=random_img_name)
            return uploaded_img_url

    def sb_get_random_cast_hash(self, users: list):
        while True:
            random_user = random.choice(users)
            user_casts = self.client.get_casts(fid=random_user.fid).casts
            if (
                len(user_casts) > 2
                and random_user.pfp.url
                != "https://imagedelivery.net/BXluQx4ige9GuW0Ia56BHw/3ffc18c3-e259-432c-8d42-5f07e140be00/rectcrop3"
            ):
                random_user_cast = random.choice(user_casts)

                return random_user_cast.hash

            time.sleep(1)

    def choose_comment_method(self):
        total_probability = sum(
            method["probability"] for method in settings.comment_methods
        )

        if not math.isclose(total_probability, 1.0, rel_tol=1e-9):
            raise Exception("Сумма вероятностей должна быть равна 1.0")

        random_num = random.random()
        cumulative_probability = 0

        for method in settings.comment_methods:
            cumulative_probability += method["probability"]
            if random_num <= cumulative_probability:
                return method["method"]

    def sb_send_comment(self, text: str, cast_hash: str):
        return self.client.post_cast(text=text, parent=cast_hash).cast

    def sb_check_comment(self, cast_hash: str, text: str):
        thread_casts = self.client.get_thread_casts(thread_hash=cast_hash)

        for i, cast in enumerate(thread_casts.casts, 1):
            if cast.text == text:
                return False
        return True

    def sb_delete_post(self, cast_hash: str):
        self.client.delete_cast(cast_hash=cast_hash)

    def change_bio_and_display_name(
        self, change_type: str, bio: str = None, display_name: str = None
    ):
        if settings.gpt_use_on_set_bio_or_name:
            match change_type:
                case "all":
                    text = self.client_gpt.get_msg(
                        content=f"Напиши мне никнейм и очень короткую биографию на 2-4 cлова на {self.language} языке нужно добавить небрежности. что бы она выглядела более натурально, например писать с маленькой буквы или допускать сленговые выражение или даже ошибки. Ответ без дополнительных кавычек и в формате: имя:биография"
                    )
                    logger.info(f"@{self.me.username} : Получили от gpt ответ {text}")
                    display_name, bio = text.split(":")
                    logger.info(
                        f"@{self.me.username} : Заполняем имя {display_name} и био {bio} с помощью GPT"
                    )

                case "display_name":
                    text = self.client_gpt.get_msg(
                        content="Напиши мне никнейм. Добавь небрежности, что бы он выглядел более натурально, например напиши с маленькой буквы или можно использовать сленговые выражение или даже ошибки. В ответ верни только никнейм без дополнительных кавычек и дополнительных комментариев."
                    )
                    display_name = text
                    logger.info(
                        f"@{self.me.username} : Заполняем имя {display_name} с помощью GPT"
                    )

                case "bio":
                    text = self.client_gpt.get_msg(
                        content=f"Напиши мне очень короткую биографию на 2-4 лова на {self.language} языке нужно добавить небрежности. что бы она выглядела более натурально, например писать с маленькой буквы или допускать сленговые выражение или даже ошибки. ответ верни только биография без дополнительных кавычек и дополнительных комментариев"
                    )
                    bio = text
                    logger.info(
                        f"@{self.me.username} : Заполняем био {bio} с помощью GPT"
                    )

                case _:
                    logger.error("Неизвестная ошибка.")
        else:
            if display_name and bio:
                logger.info(
                    f"@{self.me.username} : Заполняем имя {display_name} и био {bio} с account_data.txt"
                )

            elif display_name and not bio:
                logger.info(
                    f"@{self.me.username} : Заполняем имя {display_name} с account_data.txt"
                )

            elif bio and not display_name:
                logger.info(
                    f"@{self.me.username} : Заполняем био {bio} с account_data.txt"
                )

        self.client.set_bio_and_display_name(
            bio=bio if bio else self.me.profile.bio.text,
            display_name=display_name if display_name else self.me.display_name,
        )

        logger.success(f"@{self.me.username} : успешно заполнили профиль!")

    def send_random_post(self):
        if settings.gpt_use_on_post:
            logger.info(
                f"@{self.me.username} : Делаем пост через ГПТ на {self.language} языке"
            )
            retry = 0

            while True:
                retry += 1
                logger.info(
                    f"Попытка {retry}/{settings.max_retry} | Лимит символов {self.post_max_symbol_limit} | Язык {self.language}"
                )
                try:
                    text = self.client_gpt.get_post(
                        language=self.language,
                        max_symbol_limit=self.post_max_symbol_limit,
                    )

                    logger.info(f"{text} -> ({len(text)})")
                    if 10 < len(text) < self.post_max_symbol_limit:
                        break
                    else:
                        logger.error(
                            f"@{self.me.username} : ('{text}' -> {len(text)} символов) : Длина сообщения которое написал gpt меньше 10 или больше {self.post_max_symbol_limit} символов, попробуем сделать запрос к гпт еще раз."
                        )

                        if retry > settings.max_retry:
                            logger.warrning(
                                f"@{self.me.username} : Сделали максимальное кол-во попыток для получения нужного поста у gpt для написания этому пользователю. Скипаем и идем к следующему."
                            )
                            break

                except Exception as e:
                    logger.error(f"При запросе к GPT случилась ошибка: {e}")
                    logger.info("Поспим 10 секунд и попробуем еще раз")
                    time.sleep(10)
                    if retry > settings.max_retry:
                        break
        else:
            text = self.text
            logger.info(f"@{self.me.username} : Берем пост из post.txt")

        img_url = self.get_random_img()

        for i, _ in enumerate(range(settings.max_retry), 1):
            try:
                if img_url:
                    self.client.post_cast(text=text, embeds=img_url)
                else:
                    self.client.post_cast(text=text)

                break

            except Exception as e:
                logger.error(e)
                rnd_sleep_time = random.randint(5, 15)

                logger.error(
                    f"@{self.me.username} : Ошибка при отправке рандомного поста ({text}), попытка {i}/{settings.max_retry} - спим {rnd_sleep_time} и попробуем еще раз"
                )

                time.sleep(rnd_sleep_time)
                if i == settings.max_retry:
                    raise Exception(
                        f"Так и не получилось отправить пост за {settings.max_retry} попыток"
                    )

        random_time_sleep = random.randint(
            settings.sl_inside_account[0], settings.sl_inside_account[1]
        )

        logger.success(
            f"@{self.me.username} : Разместили рандомный пост '{text}', спим {random_time_sleep} сек"
        )

        time.sleep(random_time_sleep)

    def send_comment_on_cast(self, users: List):
        how_random_user = random.randint(
            settings.max_user_for_comment[0], settings.max_user_for_comment[1]
        )

        logger.info(
            f"@{self.me.username} : Пишем коменты на посты у {how_random_user} пользователей"
        )

        for _ in range(how_random_user):
            random_user = random.choice(users)

            how_random_comment = random.randint(
                settings.max_comment_per_user[0], settings.max_comment_per_user[1]
            )

            user_casts = self.client.get_casts(fid=random_user.fid).casts

            logger.info(
                f"@{self.me.username} : Пишем коменты на {how_random_comment} поста(-ов) или меньше у пользователя @{random_user.username}"
            )

            if how_random_comment > len(user_casts):
                logger.warning(
                    f"@{self.me.username} : хотели написать коменты на {how_random_comment} постов, но у этого пользователя (@{random_user.username}) только {len(user_casts)} поста."
                )

                how_random_comment = len(user_casts)

            random_user_casts = random.sample(user_casts, how_random_comment)

            for i, cast in enumerate(random_user_casts, 1):
                if len(cast.text) > 6:
                    if settings.gpt_use_on_comment_post:
                        logger.info(
                            f"@{self.me.username} : {i}/{len(random_user_casts)} Делаем тематический комент к посту"
                        )

                        retry = 0
                        while True:
                            retry += 1
                            logger.info(
                                f"Попытка {retry}/{settings.max_retry} | Лимит символов {self.post_max_symbol_limit} | Язык {self.language}"
                            )
                            try:
                                if settings.gpt_use_language_on_comment_post:
                                    text = (
                                        self.client_gpt.get_context_comment_by_language(
                                            post=cast.text,
                                            language=self.language,
                                            max_symbol_limit=self.post_max_symbol_limit,
                                        )
                                    )
                                else:
                                    text = self.client_gpt.get_context_comment(
                                        post=cast.text,
                                        max_symbol_limit=self.post_max_symbol_limit,
                                    )

                                logger.info(f"{text} -> ({len(text)})")
                                if 10 < len(text) < self.post_max_symbol_limit:
                                    break
                                else:
                                    logger.error(
                                        f"@{self.me.username} : ('{text}' -> {len(text)} символов) : Длина сообщения которое написал gpt меньше 10 символов или больше {self.post_max_symbol_limit} символов, попробуем сделать запрос к гпт еще раз."
                                    )

                                    if retry > settings.max_retry:
                                        logger.warning(
                                            f"@{self.me.username} : Сделали максимальное кол-во попыток для получения нужного комента у gpt для написания этому пользователю. Скипаем и идем к следующему."
                                        )
                                        break

                            except Exception as e:
                                logger.error(f"При запросе к GPT случилась ошибка: {e}")
                                logger.info("Поспим 10 секунд и попробуем еще раз")
                                time.sleep(10)
                                if retry > settings.max_retry:
                                    break
                    else:
                        raise Exception("Писать коменты к постам можно только с ГПТ")

                    img_url = self.get_random_img()
                    chosen_method = self.choose_comment_method()

                    for i, _ in enumerate(range(settings.max_retry), 1):
                        try:
                            if chosen_method == "post_cast_comment":
                                if img_url:
                                    self.client.post_cast(
                                        text=text, parent=cast.hash, embeds=img_url
                                    )
                                else:
                                    self.client.post_cast(text=text, parent=cast.hash)

                            elif chosen_method == "repost_cast":
                                self.client.repost_cast(
                                    cast_hash=cast.hash, user_fid=random_user.fid
                                )
                            elif chosen_method == "repost_cast_uqote":
                                self.client.repost_cast_uqote(
                                    username=cast.author.username,
                                    cast_hash=cast.hash,
                                    text=text,
                                    user_fid=random_user.fid,
                                )

                            logger.success(
                                f"@{self.me.username} : Написали тематический коммент({text}) на рандомный пост ({cast.text}) от @{cast.author.username} это пост {i}/{len(random_user_casts)}"
                            )
                            break

                        except Exception as e:
                            logger.error(e)
                            rnd_sleep_time = random.randint(5, 15)

                            logger.error(
                                f"@{self.me.username} : Ошибка при написании тематического комметария ({text}), попытка {i}/{settings.max_retry} - спим {rnd_sleep_time} и попробуем еще раз"
                            )

                            time.sleep(rnd_sleep_time)
                            if i == settings.max_retry:
                                raise Exception(
                                    f"Так и не получилось отпавить тематический комментарий за {settings.max_retry} попыток"
                                )

                else:
                    logger.info(
                        f"@{self.me.username} : {i}/{len(random_user_casts)} Пост '{cast.text}' меньше 6 символов, на такие не пишем тематические коменты"
                    )

                random_time_sleep = random.randint(
                    settings.sl_inside_account[0], settings.sl_inside_account[1]
                )

                logger.info(
                    f"@{self.me.username} : {i}/{len(random_user_casts)} спим {random_time_sleep} сек между постами"
                )
                time.sleep(random_time_sleep)

    def random_like(self, users: List):
        how_random_user = random.randint(
            settings.max_user_for_like[0], settings.max_user_for_like[1]
        )

        logger.info(
            f"@{self.me.username} : Лайкаем посты у {how_random_user} пользователей"
        )

        for _ in range(how_random_user):
            random_user = random.choice(users)

            how_random_likes = random.randint(
                settings.max_likes_per_user[0], settings.max_likes_per_user[1]
            )

            user_casts = self.client.get_casts(fid=random_user.fid).casts

            logger.info(
                f"@{self.me.username} : Лайкаем {how_random_likes} поста(-ов) или меньше у пользователя @{random_user.username}"
            )

            if how_random_likes > len(user_casts):
                logger.warning(
                    f"@{self.me.username} : хотели залайкать {how_random_likes}, но у этого пользователя (@{random_user.username}) только {len(user_casts)} поста."
                )

                how_random_likes = len(user_casts)

            random_user_casts = random.sample(user_casts, how_random_likes)

            for i, cast in enumerate(random_user_casts, 1):
                for ii, _ in enumerate(range(settings.max_retry), 1):
                    try:
                        self.client.like_cast(cast.hash, cast_fid=random_user.fid)
                        break

                    except Exception as e:
                        logger.error(e)
                        rnd_sleep_time = random.randint(5, 15)

                        logger.error(
                            f"@{self.me.username} : Ошибка при отправке рандомного лайка, попытка {ii}/{settings.max_retry} - спим {rnd_sleep_time} и попробуем еще раз"
                        )

                        time.sleep(rnd_sleep_time)
                        if ii == settings.max_retry:
                            raise Exception(
                                f"Так и не получилось отправить лайк за {settings.max_retry} попыток"
                            )

                random_time_sleep = random.randint(
                    settings.sl_inside_account[0], settings.sl_inside_account[1]
                )

                logger.success(
                    f"@{self.me.username} : Залайкали рандомный пост от @{cast.author.username} это лайк {i}/{len(random_user_casts)}, спим {random_time_sleep} сек"
                )

                time.sleep(random_time_sleep)

    def random_follow(self, users: List):
        how_follow = random.randint(
            settings.max_followers[0], settings.max_followers[1]
        )

        random_users = random.sample(users, how_follow)

        for i, user in enumerate(random_users, 1):
            for ii, _ in enumerate(range(settings.max_retry), 1):
                try:
                    self.client.follow_user(user.fid)
                    break

                except Exception as e:
                    logger.error(e)
                    rnd_sleep_time = random.randint(5, 15)

                    logger.error(
                        f"@{self.me.username} : Ошибка при отправке рандомной подписки, попытка {ii}/{settings.max_retry} - спим {rnd_sleep_time} и попробуем еще раз"
                    )

                    time.sleep(rnd_sleep_time)
                    if ii == settings.max_retry:
                        raise Exception(
                            f"Так и не получилось подписаться на радономного человека за {settings.max_retry} попыток"
                        )

            random_time_sleep = random.randint(
                settings.sl_inside_account[0], settings.sl_inside_account[1]
            )

            logger.success(
                f"@{self.me.username} : подписались на @{user.username} это подписка {i}/{len(random_users)}, спим {random_time_sleep} сек"
            )

            time.sleep(random_time_sleep)

    def print_streak_status(self):
        streak_status = self.client.get_streak_status()
        if streak_status:
            logger.info(
                f"@{self.me.username} : Сегодня делали?: {streak_status.metadata.already_casted_today} | Канал: {streak_status.channel.name} | Streak: {streak_status.streak_count} дней | Начали страйк: {self.timestamp_convert(ts=streak_status.metadata.started_at_timestamp)} | Следующий страйк после: {self.timestamp_convert(ts=streak_status.metadata.expires_at_timestamp)} | Последний раз продляли: {self.timestamp_convert(ts=streak_status.metadata.latest_window_start_timestamp)}"
            )
        else:
            logger.warning(
                f"@{self.me.username} : Нету страйк статуса на этом аккаунте."
            )

    def strike_autopilot(self):
        streak_status = self.client.get_streak_status()

        with open("data/const/streak_posts.txt", "r", encoding="utf-8") as f:
            streak_posts = f.read().splitlines()
        streak_random_post = random.choice(streak_posts)

        if streak_status:
            logger.info(
                f"@{self.me.username} : STREAK уже активрован, проверяем можем ли мы его продлить."
            )
            if not streak_status.metadata.already_casted_today:
                logger.info(
                    f"@{self.me.username} : Продлеваем STREAK на один день. Пишем пост: {streak_random_post}"
                )

                time.sleep(random.randint(1, 3))
                self.client.post_cast(
                    text=streak_random_post, channel_key=streak_status.channel.key
                )
                logger.success(f"@{self.me.username} : Продлили страйк!")
            else:
                logger.warning(
                    f"@{self.me.username} : Продление еще не доступно, попробуйте позже."
                )
        else:
            following_channels = self.client.get_user_following_channels()
            time.sleep(random.randint(1, 3))
            streak_channel = random.choice(following_channels)
            logger.warning(
                f"@{self.me.username} : STREAK еще не активирован, запускам активацию. Выбираем рандомный канал для страйка из подписок аккаунта: {streak_channel.key} и пишем пост: {streak_random_post}"
            )
            self.client.start_stike(channel_key=streak_channel.key)
            time.sleep(random.randint(1, 3))
            self.client.post_cast(
                text=streak_random_post, channel_key=streak_channel.key
            )
            logger.success(f"@{self.me.username} : Активировали страйк!")

    def random_actions(self, users: List):
        methods = [
            ("рандом пост", self.send_random_post, ()),
            ("рандом лайк", self.random_like, (users,)),
            ("рандом подписка", self.random_follow, (users,)),
            ("рандомный комент", self.send_comment_on_cast, (users,)),
        ]

        random.shuffle(methods)
        i = 0

        for name, method, params in methods:
            i += 1
            method(*params)

            random_time_sleep = random.randint(
                settings.sl_inside_account[0], settings.sl_inside_account[1]
            )

            logger.info(
                f"@{self.me.username} Закончили {i}/{len(methods)} '{name}', спим внутри random_actions между действиями {random_time_sleep} сек"
            )
            logger.info("#" * 50)

            if i < len(methods):
                time.sleep(random_time_sleep)

    def custom_random_actions(self, users: List, work_methods: Union[List, str]):
        methods = {
            "random_like": ("рандом лайк", self.random_like, (users,)),
            "random_post": ("рандом пост", self.send_random_post, ()),
            "random_follow": ("рандом подписка", self.random_follow, (users,)),
            "random_comment": (
                "рандом комменты к постам",
                self.send_comment_on_cast,
                (users,),
            ),
        }

        if isinstance(work_methods, list):
            random.shuffle(work_methods)
        else:
            work_methods = [
                work_methods,
            ]

        for i, choise_method in enumerate(work_methods, 1):
            name, method, params = methods[choise_method]

            method(*params)

            random_time_sleep = random.randint(
                settings.sl_inside_account[0], settings.sl_inside_account[1]
            )

            logger.info(
                f"@{self.me.username} Закончили {i}/{len(work_methods)} '{name}', спим внутри custom_random_actions между действиями {random_time_sleep} сек"
            )
            logger.info("#" * 50)

            time.sleep(random_time_sleep)

    def _request_subscriptions(
        self, attempts: int = 5, how_subscriptions_people: int = 1
    ):
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    f"{self.splayer_api_url}/request_subscriptions/",
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={
                        "fid": self.me.fid,
                        "requested_subscriptions": how_subscriptions_people,
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data["success"]:
                    return data["subscriptions"]
                else:
                    logger.error(
                        f"Попытка {attempt}/{attempts} не удалась: {data.get('message', 'Неизвестная ошибка')}"
                    )
                    if attempt < attempts:
                        logger.info("Повторная попытка через 5 секунд...")
                        time.sleep(5)
                    else:
                        logger.error(
                            "Достигнуто максимальное количество попыток. Запрос не удался."
                        )
                        return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Произошла ошибка при выполнении запроса: {e}")
                if attempt < attempts:
                    logger.info(
                        f"Попытка {attempt}/{attempts}. Повторная попытка через 5 секунд..."
                    )
                    time.sleep(5)
                else:
                    logger.error(
                        "Достигнуто максимальное количество попыток. Запрос не удался."
                    )
                    return None
            except json.JSONDecodeError:
                logger.error(
                    f"Получен некорректный JSON. Попытка {attempt}/{attempts}."
                )
                if attempt < attempts:
                    logger.info("Повторная попытка через 5 секунд...")
                    time.sleep(5)
                else:
                    logger.error(
                        "Достигнуто максимальное количество попыток. Запрос не удался."
                    )
                    return None

    def _confirm_subscriptions(self, attempts: int = 5):
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    f"{self.splayer_api_url}/confirm_subscriptions/",
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={"fid": self.me.fid},
                )
                response.raise_for_status()
                data = response.json()
                if data.get("success"):
                    return data
                else:
                    logger.error(
                        f"Попытка {attempt}/{attempts} не удалась: {data.get('message', 'Неизвестная ошибка')}"
                    )
                    if attempt < attempts:
                        logger.info("Повторная попытка через 5 секунд...")
                        time.sleep(5)
                    else:
                        logger.error(
                            "Достигнуто максимальное количество попыток. Запрос не удался."
                        )
                        return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Произошла ошибка при выполнении запроса: {e}")
                if attempt < attempts:
                    logger.info(
                        f"Попытка {attempt}/{attempts}. Повторная попытка через 5 секунд..."
                    )
                    time.sleep(5)
                else:
                    logger.error(
                        "Достигнуто максимальное количество попыток. Запрос не удался."
                    )
                    return None
            except json.JSONDecodeError:
                logger.error(
                    f"Получен некорректный JSON. Попытка {attempt} из {attempts}."
                )
                if attempt < attempts:
                    logger.info("Повторная попытка через 5 секунд...")
                    time.sleep(5)
                else:
                    logger.error(
                        "Достигнуто максимальное количество попыток. Запрос не удался."
                    )
                    return None

    def add_account_on_splayers(self):
        self._request_subscriptions()

        logger.success(
            f"@{self.me.username} : Успешно добавил акаунт в @SPLAYERLABSBOT"
        )

    def follow_account_from_splayers(self):
        how_subscriptions_people = random.randint(
            settings.count_for_subscriptions[0], settings.count_for_subscriptions[1]
        )

        subscriptions_list = self._request_subscriptions(
            how_subscriptions_people=how_subscriptions_people
        )

        logger.info(
            f"@{self.me.username} : Получаем {how_subscriptions_people} пользователей из @SPLAYERLABSBOT для подписки"
        )

        for i, subscriptions_user in enumerate(subscriptions_list, start=1):
            self.client.follow_user(fid=subscriptions_user["fid"])

            logger.success(
                f"@{self.me.username} : Успешно подписался на {subscriptions_user['link']} {i}/{len(subscriptions_list)}"
            )

            random_time_sleep = random.randint(
                settings.sl_inside_account[0], settings.sl_inside_account[1]
            )

            if i < len(subscriptions_list):
                logger.info(
                    f"@{self.me.username} : Спим {random_time_sleep} сек между подписками на аккаунты @SPLAYERLABSBOT {i}/{len(subscriptions_list)}"
                )
                time.sleep(random_time_sleep)

        logger.info(
            f"@{self.me.username} : Подписались на все {len(subscriptions_list)} аккаунтов, которые предоставил @SPLAYERLABSBOT. Запрашиваем подтверждение в боте."
        )

        confirm_subs = self._confirm_subscriptions()

        if confirm_subs:
            logger.success(
                f"@{self.me.username} : Успешно выполнили задание с @SPLAYERLABSBOT и получили подтверждение для этого аккаунта."
            )

        else:
            logger.error(
                f"@{self.me.username} : Произошла ошибка при получении подтверждения по заданию из @SPLAYERLABSBOT для этого аккаунта."
            )
