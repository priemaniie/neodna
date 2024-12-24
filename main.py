import questionary
from loguru import logger

from config import settings
from manager_account import WarpManager
from utils import prepare_data_on_db, show_table

if __name__ == "__main__":
    bd_menu_str = f"из базы данных '{settings.db_file_name}': db_use = True"
    choice = questionary.select(
        "Что будем делать для каждого аккаунта Warpcast?",
        choices=[
            f"------ СТАНДАРТНЫЙ ФУНКЦИОНАЛ (Аккаунты используем {bd_menu_str if settings.db_use else 'из private_seeds.txt, proxy.txt, roles.txt, language.txt: db_use = False'})",
            f"1. Пишем случайный пост {'c помощью GPT gpt_use_on_post = True' if settings.gpt_use_on_post else 'из posts.txt gpt_use_on_post = False'}",
            "2. Ставим лайки на случайные посты пользователей",
            "3. Подписываемся на случайные аккаунты",
            "4. Пишем тематический комент с помощью GPT и/или делаем репост к себе и/или делаем репост к себе со своим коментом. (смотри в настройки comment_methods)",
            " " * 15,
            f"------ МАРШРУТЫ С РАНДОМОМ (Аккаунты используем {bd_menu_str if settings.db_use else 'из private_seeds.txt, proxy.txt, roles.txt, language.txt: db_use = False'})",
            f"5. Делаем rnd пост, пишем rnd комент на rnd пост, ставим rnd лайки, подписываемся на rnd аккаунты в случайном порядке для каждого аккаунта. Данные {'c помощью GPT' if settings.gpt_use_on_comment_post else 'из posts.txt'}",
            f"6. Запускаем БОЛЬШОЙ рандомный модуль, внимательно изучи настройки перед его запуском. Посты {'c помощью GPT gpt_use_on_post = True' if settings.gpt_use_on_post else 'из posts.txt gpt_use_on_post = False'}. Коменты {'c помощью GPT' if settings.gpt_use_on_comment_post else 'из posts.txt'}",
            " " * 15,
            f"------ STRIKE МОДУЛЬ (Аккаунты используем {bd_menu_str if settings.db_use else 'из private_seeds.txt, proxy.txt, roles.txt, language.txt: db_use = False'})",
            "7. Автопилот STRIKE (Посты из strike_posts.txt) (Бежит по всем аккаунтам и если есть возможность стартовать страйк или продлить страйк на день - делает его.)",
            "8. Проверка STRIKE статуса на аккаунтах. Печатает страйк статус по каждому аккаунту. Просто чекается статус без каких либо действий.",
            " " * 15,
            f"------ ЗАПОЛНЕНИЕ АККАУНТА (Аккаунты используем {bd_menu_str if settings.db_use else 'из private_seeds.txt, proxy.txt, roles.txt, language.txt: db_use = False'})",
            f"9. Заполняем имена {'c помощью GPT gpt_use_on_set_bio_or_name = True' if settings.gpt_use_on_set_bio_or_name else 'из account_data.txt gpt_use_on_set_bio_or_name = False'}",
            f"10. Заполняем био {'c помощью GPT gpt_use_on_set_bio_or_name = True' if settings.gpt_use_on_set_bio_or_name else 'из account_data.txt gpt_use_on_set_bio_or_name = False'}",
            f"11. Заполняем имена и био {'c помощью GPT gpt_use_on_set_bio_or_name = True' if settings.gpt_use_on_set_bio_or_name else 'из account_data.txt gpt_use_on_set_bio_or_name = False'}",
            " " * 15,
            f"------ ЧЕКЕР БАНОВ (Аккаунты используем {bd_menu_str if settings.db_use else 'из private_seeds.txt, proxy.txt, roles.txt, language.txt: db_use = False'})",
            "12. Проверить теневой бан на аккаунтах (Результат записывается в бд, нужно минимум 2 аккаунта для работы)",
            " " * 15,
            "------ КОНТРОЛЬ АККАУНТОВ/БД (Используйте Базу Данных только если понимаете что делаете. Внимательно проверте, что у вас добавлены private_seeds.txt, proxy.txt (login:pass@ip:port), roles.txt для использования gpt)",
            "13. Cоздать базу данных. Софт можно использовать и без этой бд, она создается для вашего удобства.",
            "14. Показать таблицу бд (Она так-же доступна в папке bd. Через vscode откройте фаил, выделите все, правой кнопкой, форматировать документ.)",
            " " * 15,
            "------ ✨🆕✨ АВТОМАТИЧЕСКИЙ МАРШРУТ В ПАРТНЕРСТВЕ С @SPLAYERLABSBOT",
            "15. Добавляем каждый аккаунт в базу @SPLAYERLABSBOT (Можно смело запускать, если аккаунт будет уже добавлен, его просто скипнет или можете сразу запустить следующий маршрут)",
            "16. Выполняем задание по подпискам из @SPLAYERLABSBOT для каждого аккаунта (Можно запустить новый аккаунт, если он не добавлен в бота и у него нету задания, аккаунт автоматически добавится и получит задания для выполнения)",
            " " * 15,
            "0. Выход",
        ],
        instruction="(Используйте стрелки для переключения)",
        pointer="🥎",
    ).ask()

    match choice.split(".")[0]:
        case "1":
            client = WarpManager()
            client.post_random_message()

        case "2":
            client = WarpManager()
            client.like_random_posts()

        case "3":
            client = WarpManager()
            client.follow_random_accounts()

        case "4":
            client = WarpManager()
            client.post_random_comment()

        case "5":
            client = WarpManager()
            client.perform_all_randomly()

        case "6":
            client = WarpManager()
            client.perform_custom_randomly()

        case "7":
            client = WarpManager()
            client.streak_autopilot()

        case "8":
            client = WarpManager()
            client.print_streak_status()

        case "9":
            client = WarpManager()
            client.perform_set_display_name()

        case "10":
            client = WarpManager()
            client.perform_set_bio()

        case "11":
            client = WarpManager()
            client.perform_set_display_name_and_bio()

        case "12":
            client = WarpManager()
            client.shadow_ban_check()

        case "13":
            prepare_data_on_db()
            logger.warning(
                "Не забудь в конфиге поставить db_use = True, что бы данные брались из бд. Перезапустите софт, что начать работу с аккаунтами."
            )

        case "14":
            show_table()

        case "15":
            client = WarpManager()
            client.perform_add_account_on_splayers()

        case "16":
            client = WarpManager()
            client.perform_follow_account_from_splayers()

        case "0":
            pass

        case _:
            logger.error("Вы выбрали неизвестный вариант")
