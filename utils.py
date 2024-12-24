import itertools
import os

import questionary
import requests
from loguru import logger
from tabulate import tabulate
from tinydb import JSONStorage, TinyDB

from config import settings
from models import Account
from warp import Warp


def truncate(value, length=10):
    if isinstance(value, str) and len(value) > length:
        return value[:length]
    return value


def print_on_table(data: list, headers: list):
    truncated_data = [
        [i] + [truncate(cell) for cell in row] for i, row in enumerate(data, 1)
    ]
    table = tabulate(truncated_data, headers, tablefmt="grid")
    print(table)


def show_table():
    db_patch = os.path.join(settings.db_dir, settings.db_file_name)
    db = TinyDB(db_patch, storage=JSONStorage, ensure_ascii=False, encoding="utf-8")
    table_data = []
    headers = None
    for data in db.all():
        account = Account.model_validate(data)

        if not headers:
            headers = account.to_list_headers()
            headers.insert(0, "#")

        table_data.append(account.to_list_value())

    print_on_table(data=table_data, headers=headers)


def prepare_data_on_db():
    db_dir = settings.db_dir
    db_file_name = settings.db_file_name
    db_name, db_extension = db_file_name.split(".")
    db_path = os.path.join(db_dir, db_name + "." + db_extension)

    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    if os.path.exists(db_path):
        db = TinyDB(db_path, storage=JSONStorage, ensure_ascii=False, encoding="utf-8")
        all_records = db.all()

        if len(all_records) > 0:
            usernames = [record.get("username") for record in all_records]
            logger.error(
                f"У вас уже есть созданная БД с {len(all_records)} аккаунтов: {', '.join(usernames)}"
            )

            choice = questionary.select(
                "Что вы хотите сделать?",
                choices=[
                    "1. Дописать аккаунты в текущую базу данных",
                    "2. Создать новую базу данных",
                ],
                instruction="(Используйте стрелки для переключения)",
                pointer="🥎",
            ).ask()

            if choice.split(".")[0] == "2":
                i = 1
                while os.path.exists(
                    os.path.join(db_dir, f"{db_name}{i}.{db_extension}")
                ):
                    i += 1

                db_path = os.path.join(db_dir, f"{db_name}{i}.{db_extension}")
                db = TinyDB(
                    db_path, storage=JSONStorage, ensure_ascii=False, encoding="utf-8"
                )

                logger.success(f"Создана новая база данных: {db_path}")

            elif choice.split(".")[0] == "1":
                logger.success(f"Дописываем в текущую базу данных: {db_path}")

    else:
        db = TinyDB(db_path, storage=JSONStorage, ensure_ascii=False, encoding="utf-8")

    try:
        with open("data/const/private_seeds.txt", "r", encoding="utf-8") as f:
            private_seeds = f.read().splitlines()
    except FileNotFoundError:
        logger.error("Файл private_seeds.txt не найден!")
        return

    if not private_seeds:
        raise ValueError("Файл с сидками не может быть пустым!")

    try:
        with open("data/const/languages.txt", "r", encoding="utf-8") as f:
            language = f.read().splitlines()
            language_cycle = itertools.cycle(language)
        if not language:
            logger.warning(
                "Вы не добавили языки, создаю бд без языков, функции гпт будут работать не стабильно."
            )
    except FileNotFoundError:
        language = []
        language_cycle = itertools.cycle(language)

    if settings.proxy:
        try:
            with open("data/const/proxy.txt", "r", encoding="utf-8") as f:
                proxys = f.read().splitlines()
                proxy_cycle = itertools.cycle(proxys)
            if not proxys:
                logger.warning(
                    "Вы включили прокси в конфиге, но не добавили прокси в proxy.txt, создаю бд без проксей."
                )
        except FileNotFoundError:
            proxys = []
            proxy_cycle = itertools.cycle(proxys)
    else:
        proxys = []
        proxy_cycle = itertools.cycle(proxys)

    try:
        with open("data/gpt/roles.txt", "r", encoding="utf-8") as f:
            roles = f.read().splitlines()
            role_cycle = itertools.cycle(roles)
        if not roles:
            logger.warning("Вы не добавили роли для chat-gpt, создаем бд без ролей.")
    except FileNotFoundError:
        roles = []

    table_data = []
    headers = None
    logger.debug(f"Добавляем в базу данных {len(private_seeds)} аккаунта(-ов)")
    for i, ps in enumerate(private_seeds, 1):
        proxy = next(proxy_cycle, None)
        role = next(role_cycle, None)
        language, post_max_symbol_limit = next(language_cycle, None).split(":")

        account = Account(ps=ps, proxy=proxy, role=role)
        client = Warp(account=account)
        account = Account(
            display_name=client.me.display_name,
            username=client.me.username,
            bio=client.me.profile.bio.text,
            language=language,
            post_max_symbol_limit=post_max_symbol_limit,
            follower_count=client.me.follower_count,
            following_count=client.me.following_count,
            ps=ps,
            proxy=proxy,
            role=role,
        )

        db.insert(account.model_dump())
        logger.info(
            f"Добавили {i}/{len(private_seeds)} - {account.display_name} (@{account.username})"
        )

        if not headers:
            headers = account.to_list_headers()
            headers.insert(0, "#")

        table_data.append(account.to_list_value())

        if settings.mobile_proxy:
            logger.warning("Меняем ip у мобильной прокси при добавлении аккаунтов в бд")
            print(requests.get(settings.mobile_change_link).text)

    print_on_table(data=table_data, headers=headers)


def prepare_data_from_txt():
    with open("data/const/private_seeds.txt", "r", encoding="utf-8") as f:
        private_seeds = f.read().splitlines()

    if not private_seeds:
        raise ValueError("Фаил с сидками не может быть пустым!")

    try:
        with open("data/const/languages.txt", "r", encoding="utf-8") as f:
            language = f.read().splitlines()
            language_cycle = itertools.cycle(language)
        if not language:
            logger.warning(
                "Вы не добавили языки, создаю бд без языков, функции гпт будут работать не стабильно."
            )
    except FileNotFoundError:
        language = []

    try:
        with open("data/const/proxy.txt", "r", encoding="utf-8") as f:
            proxys = f.read().splitlines()
            proxy_cycle = itertools.cycle(proxys)
        if not proxys:
            logger.warning("Вы не добавили прокси, создаю бд без проксей.")
    except FileNotFoundError:
        proxys = []

    try:
        with open("data/gpt/roles.txt", "r", encoding="utf-8") as f:
            roles = f.read().splitlines()
            role_cycle = itertools.cycle(roles)
        if not roles:
            logger.warning("Вы не добавили роли для chat-gpt, создаем бд без ролей.")
    except FileNotFoundError:
        roles = []

    account_list = []
    for i, ps in enumerate(private_seeds, 1):
        proxy = next(proxy_cycle, None)
        role = next(role_cycle, None)
        language, max_symbol_limit = next(language_cycle, None).split(":")
        account_list.append(
            Account(
                ps=ps,
                proxy=proxy,
                role=role,
                language=language,
                post_max_symbol_limit=max_symbol_limit,
            )
        )

    return account_list
