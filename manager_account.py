import itertools
import os
import random
import time

import requests
from loguru import logger
from tinydb import JSONStorage, Query, TinyDB

from config import settings
from models import Account
from utils import prepare_data_from_txt
from warp import Warp


class WarpManager:
    def __init__(self):
        if settings.db_use:
            db_patch = os.path.join(settings.db_dir, settings.db_file_name)
            self.db = TinyDB(
                db_patch, storage=JSONStorage, ensure_ascii=False, encoding="utf-8"
            )
            self.work_accounts = [Account(**item) for item in self.db.all()]
        else:
            self.work_accounts = prepare_data_from_txt()
        self.users = None
        self.work_methods = None
        self.account_data_str = None

    def update_db(self, address: str, variable_name: str, variable):
        query = Query()
        result = self.db.get(query.address == address)
        if result:
            self.db.update({variable_name: variable}, doc_ids=[result.doc_id])

    def random_sleep(self, name: str, text: str = None):
        rnd_time = random.randint(
            settings.sl_between_account[0], settings.sl_between_account[1]
        )

        logger.info(f"{name} : спим {rnd_time} сек, {text}")
        time.sleep(rnd_time)

    def shadow_ban_check(self):
        with open("data/const/posts.txt", "r", encoding="utf-8") as f:
            posts = f.read().splitlines()

        logger.debug(
            f"Запустили чекер на {len(self.work_accounts)} аккаунтах. Наберитесь терпение, 1 акк проверяется примерно 20 секунд."
        )

        success = 0
        shadow_ban = 0

        if len(self.work_accounts) < 2:
            raise Exception("У вас должно быть минимум 2 аккаунта, для этой функции.")

        for i, (current_account, next_account) in enumerate(
            zip(
                self.work_accounts,
                itertools.cycle(self.work_accounts[1:] + self.work_accounts[:1]),
            ),
            1,
        ):
            text = posts.pop(random.randint(0, len(posts) - 1))
            client = Warp(account=current_account, text=text)

            if not self.users:
                self.users = client.get_users(total_limit=settings.how_get_users)

            thread_cast_hash = client.sb_get_random_cast_hash(users=self.users)
            time.sleep(1)
            controll_post = client.sb_send_comment(
                text=text, cast_hash=thread_cast_hash
            )
            time.sleep(1)
            client_next = Warp(account=next_account)

            time.sleep(1)
            check_status = client_next.sb_check_comment(
                cast_hash=thread_cast_hash, text=text
            )

            if settings.db_use:
                self.update_db(
                    address=current_account.address,
                    variable_name="shadow_ban",
                    variable=check_status,
                )

            if check_status:
                logger.error(f"{i}. {client.me.username} : Под теневым баном :(")
                shadow_ban += 1

            else:
                logger.success(f"{i}. {client.me.username} : Без теневого бана!")
                success += 1

            time.sleep(5)
            client.sb_delete_post(cast_hash=controll_post.hash)

            if settings.mobile_proxy:
                logger.warning("Меняет ip у мобильной прокси.")
                print(requests.get(settings.mobile_change_link).text)

            else:
                if i < len(self.work_accounts):
                    sl_random_time = random.randint(5, 15)
                    logger.info(f"Спим между аками {sl_random_time} секунд")
                    time.sleep(sl_random_time)

        logger.debug("-" * 50)
        logger.debug(
            f"Итог: под теневым баном {shadow_ban}({shadow_ban/len(self.work_accounts)*100}%)/{len(self.work_accounts)}"
        )

    def perform_action(self, action, action_type, sleep_text):
        iter = 0

        while True:
            iter += 1
            with open("data/const/posts.txt", "r", encoding="utf-8") as f:
                posts = f.read().splitlines()

                if settings.before_start_shuffle_ps_list:
                    random.shuffle(self.work_accounts)
                    logger.info("Мешаем аккаунты перед стартом.")

            if settings.before_start_shuffle_image_list:
                random.shuffle(self.work_accounts)
                logger.info("Мешаем картинки перед стартом.")

            if not settings.gpt_use_on_set_bio_or_name:
                if action_type in [
                    "perform_set_display_name_and_bio",
                    "perform_set_bio",
                    "perform_set_display_name",
                ]:
                    with open(
                        "data/const/account_data.txt", "r", encoding="utf-8"
                    ) as f:
                        account_data = f.read().splitlines()
                    account_data_cycle = itertools.cycle(account_data)

            if action_type == "perform_custom_randomly":
                work_methods_cycle = itertools.cycle(settings.actions_list)

            for i, account in enumerate(self.work_accounts, 1):
                text = None
                try:
                    if not settings.gpt_use_on_post:
                        if settings.uniq_post_between_account:
                            text = posts.pop(random.randint(0, len(posts) - 1))
                        else:
                            text = random.choice(posts)
                    for iteration in range(1, 4):
                        try:
                            client = Warp(account=account, text=text)
                            long_str = "#" * 10
                            logger.debug(
                                f"{long_str} Start account {i}/{len(self.work_accounts)} - @{client.me.username} seed: {account.ps[:20]} прокси: {account.proxy.split('@')[1]} {long_str}"
                            )
                            break
                        except Exception as e:
                            logger.error(
                                f"Не получилось авторизоваться с {iteration}/3 попытки, спим 3 секунды и пробуем еще раз. Ошибка: {e}"
                            )
                            if iteration >= 3:
                                logger.error(
                                    f"С 3 попыток не смогли авторизоваться на аккаунте {i}/{len(self.work_accounts)} seed:{account.ps[:20]} прокси: {account.proxy}, пропускаем этот аккаунт и эти прокси. Делаем следующий. "
                                )
                                break
                            time.sleep(3)

                    if action_type not in [
                        "perform_set_display_name_and_bio",
                        "perform_set_bio",
                        "perform_set_display_name",
                        "post_random_message",
                        "print_streak_status",
                        "strike_autopilot",
                        "perform_splayers_add_account",
                        "perform_splayers_follow_account",
                    ]:
                        if not self.users:
                            self.users = client.get_users(
                                total_limit=settings.how_get_users
                            )

                    if i == 1:
                        random.shuffle(settings.actions_list)

                    if not settings.gpt_use_on_set_bio_or_name:
                        if action_type in [
                            "perform_set_display_name_and_bio",
                            "perform_set_bio",
                            "perform_set_display_name",
                        ]:
                            self.account_data_str = next(account_data_cycle)

                    if action_type == "perform_custom_randomly":
                        self.work_methods = next(work_methods_cycle)

                    if settings.shuffle_method:
                        if i % len(settings.actions_list) == 0:
                            random.shuffle(settings.actions_list)

                    action(client)

                    self.random_sleep(
                        name=client.me.username,
                        text=sleep_text,
                    )
                except Exception as e:
                    logger.error(e)
                    logger.error(
                        "Что-то пошло не так, пропускаем текущий аккаунт и идем к следующему."
                    )

                if settings.mobile_proxy:
                    logger.warning("Меняет ip у мобильной прокси.")

                    print(requests.get(settings.mobile_change_link).text)

            if not settings.infinity_mode:
                break

            logger.warning(
                f"ЗАКОНЧИЛИ {iter} КРУГ, включен бесконечный режим, поэтому стартуем заного по тем-же кошелькам"
            )

    def post_random_message(self):
        self.perform_action(
            action=lambda client: client.send_random_post(),
            sleep_text="между аккаунтами в процессе: 'Постим случайные посты'",
            action_type="post_random_message",
        )

    def print_streak_status(self):
        self.perform_action(
            action=lambda client: client.print_streak_status(),
            sleep_text="между аккаунтами в процессе: 'Печатаем статус страйков'",
            action_type="print_streak_status",
        )

    def streak_autopilot(self):
        self.perform_action(
            action=lambda client: client.strike_autopilot(),
            sleep_text="между аккаунтами в процессе: 'Страйк автопилот'",
            action_type="strike_autopilot",
        )

    def post_random_comment(self):
        self.perform_action(
            action=lambda client: client.send_comment_on_cast(users=self.users),
            sleep_text="между аккаунтами в процессе: 'Постим gpt коменты к постам'",
            action_type="post_random_comment",
        )

    def like_random_posts(self):
        self.perform_action(
            action=lambda client: client.random_like(users=self.users),
            sleep_text="между аккаунтами в процессе: 'Лайкаем случайные посты'",
            action_type="like_random_posts",
        )

    def follow_random_accounts(self):
        self.perform_action(
            action=lambda client: client.random_follow(users=self.users),
            sleep_text="между аккаунтами в процессе: 'Делаем случайные подписки'",
            action_type="follow_random_accounts",
        )

    def perform_all_randomly(self):
        self.perform_action(
            action=lambda client: client.random_actions(
                users=self.users,
            ),
            sleep_text="между аккаунтами в процессе: 'Делаем все случайные действия в рандомном порядке по очереди'",
            action_type="perform_all_randomly",
        )

    def perform_set_display_name(self):
        change_type = "display_name"
        self.perform_action(
            action=lambda client: client.change_bio_and_display_name(
                change_type=change_type,
                display_name=self.account_data_str.split(":")[0]
                if not settings.gpt_use_on_set_bio_or_name
                else None,
            ),
            sleep_text="между аккаунтами в процессе: 'Меняем имена у аккаунта'",
            action_type="perform_set_display_name",
        )

    def perform_set_bio(self):
        change_type = "bio"
        self.perform_action(
            action=lambda client: client.change_bio_and_display_name(
                change_type=change_type,
                bio=self.account_data_str.split(":")[1]
                if not settings.gpt_use_on_set_bio_or_name
                else None,
            ),
            sleep_text="между аккаунтами в процессе: 'Меняем био у аккаунта'",
            action_type="perform_set_bio",
        )

    def perform_set_display_name_and_bio(self):
        change_type = "all"
        self.perform_action(
            action=lambda client: client.change_bio_and_display_name(
                change_type=change_type,
                display_name=self.account_data_str.split(":")[0]
                if not settings.gpt_use_on_set_bio_or_name
                else None,
                bio=self.account_data_str.split(":")[1]
                if not settings.gpt_use_on_set_bio_or_name
                else None,
            ),
            sleep_text="между аккаунтами в процессе: 'Меняем имена и био у аккаунта'",
            action_type="perform_set_display_name_and_bio",
        )

    def perform_custom_randomly(self):
        self.perform_action(
            action=lambda client: client.custom_random_actions(
                users=self.users, work_methods=self.work_methods
            ),
            sleep_text="между аккаунтами в процессе: 'Делаем большой рандомный маршрут'",
            action_type="perform_custom_randomly",
        )

    def perform_add_account_on_splayers(self):
        self.perform_action(
            action=lambda client: client.add_account_on_splayers(),
            sleep_text="между аккаунтами в процессе: 'Добавляем аккаунты в @SPLAYERLABSBOT'",
            action_type="perform_splayers_add_account",
        )

    def perform_follow_account_from_splayers(self):
        self.perform_action(
            action=lambda client: client.follow_account_from_splayers(),
            sleep_text="между аккаунтами в процессе: 'Подписываемся на рандомные аккаунты из @SPLAYERLABSBOT'",
            action_type="perform_splayers_follow_account",
        )
