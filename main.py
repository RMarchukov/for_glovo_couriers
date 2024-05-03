import asyncio
import httpx
import locale
import random
import sys
import time
from datetime import datetime, timedelta
from json import JSONDecodeError

from httpx import AsyncClient, RequestError
from pytz import timezone

from core.api.glovoapp import GlovoCourier
from core.exceptions import GlovoError, AccessTokenError, InvalidCredentials, AccountBlocked
from core.exceptions import SlotTakeError
from core.models import AccountData, SlotData
from core.utils import AccountsController
from core.utils import parse_proxies, create_httpx_client
import os
from dotenv import load_dotenv


load_dotenv()
# locale.setlocale(locale.LC_ALL, 'ru_RU')
locale.setlocale(locale.LC_ALL, 'ru')
bot_token = os.environ.get("BOT_TOKEN")


def send_to_telegram(text: str, chat_id):
    httpx.post(f'https://api.telegram.org/bot{bot_token}/sendMessage',
               data={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'})


class AtExit:
    def __init__(self) -> None:
        self.funcs = []

    def register(self, name, func, args, chat_id):
        for func_item in self.funcs:
            if func_item[0] == name:
                self.funcs.remove(func_item)
                self.funcs.append([name, func, args, chat_id])
                break
        else:
            self.funcs.append([name, func, args, chat_id])

    def notify(self):
        for func_item in self.funcs:
            _, func, args, chat_id = func_item
            func(args, chat_id)


atexit_1 = AtExit()
atexit_2 = AtExit()


async def main():
    accounts_controller = AccountsController('data')

    try:
        accounts_data = accounts_controller.get_accounts()
        if not accounts_data:
            return print(f'Папка с аккаунтами пуста')
    except JSONDecodeError as error:
        return print(f'Ошибка в конфигурационном файле: {error}')

    try:
        # proxies_txt = open(input('Путь к файлу с прокси любого формата: '))
        proxies_txt = open('proxy.txt')
        proxies = parse_proxies(proxies_txt.read())
        if len(proxies) < len(accounts_data):
            return print(f'В файле недостаточно прокси (min: {len(accounts_data)})')

        print(f'Найдено прокси: {len(proxies)}')
    except FileNotFoundError:
        return print('Не удалось найти файл с прокси')

    print('Формирование потоков...')

    tasks = []
    for index, proxy in enumerate(proxies):
        try:
            http_client = await create_httpx_client(proxy)
            if http_client:
                tasks.append(worker(http_client, accounts_data[index], accounts_controller, 1, 0, 0, 0))
                continue
        except IndexError:
            break

    if len(tasks) < len(accounts_data):
        return print(f'Не удалось создать потоки на каждый аккаунт изза множества нерабочих прокси')

    print(f'[{" | ".join([account_data.credentials.email for account_data in accounts_data])}] Потоки запущены')

    await asyncio.gather(*tasks)


async def worker(http_client: AsyncClient, account: AccountData, accounts_controller: AccountsController, attempt: int, successful_h, unsuccessful_h, all_hours):
    glovo = GlovoCourier(
        http_client,
        account.credentials,
        account.oauth
    )
    idname = account.credentials.email

    desired_slots: list[SlotData] = []
    block_count = 0
    try:
        if not account.oauth.access_token:
            account.oauth = await glovo.auth()
            account.profile = await glovo.profile()
            accounts_controller.update_account(account)

            print(f'[{account.credentials.email}] Успешно получили учетные данные пользователя')

        slots = await glovo.get_slots()

        for interval in account.filter.intervals:
            for slot in slots:
                if (not slot.booked) and (int(interval.start_time_sec + slot.date_ts) * 1000 <= slot.start_ts) and (
                        int(interval.end_time_sec + slot.date_ts) * 1000 >= slot.end_ts) and (
                        slot.weekday in account.filter.days) and not datetime.now().replace(tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0,
                                                                                        microsecond=0) <= (
                                datetime.fromtimestamp(slot.start_ts // 1000,
                                                       timezone('Etc/GMT-0'))) < datetime.now().replace(
                            tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0,
                                                                  microsecond=0) + timedelta(hours=1) and not datetime.now().replace(tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0,
                                                                                        microsecond=0) - timedelta(
                            hours=1) <= (
                                datetime.fromtimestamp(slot.start_ts // 1000,
                                                       timezone('Etc/GMT-0'))) < datetime.now().replace(
                            tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0, microsecond=0):
                    desired_slots.append(slot)

    except InvalidCredentials:
        return print(
            f'[{account.credentials.email}] Неверные учетные данные: {account.credentials.email}:{account.credentials.password}')
    except RequestError:
        print(f'[{account.credentials.email}] Ошибка подключения')
        return await worker(http_client, account, accounts_controller)
    except AccountBlocked as error:
        send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.', account.filter.chat_id_1)
        send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.', account.filter.chat_id_2)
        return print(f'[{account.credentials.email}] {error.message} Аккаунт заблокирован.')
    except AccessTokenError:
        if attempt > 3:
            send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.', account.filter.chat_id_1)
            send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.', account.filter.chat_id_2)
            return print(f'[{account.credentials.email}] Аккаунт заблокирован.')
        else:
            for wt in account.settings.worktimes:
                current_time = datetime.now()
                hours = current_time.hour
                minutes = current_time.minute
                seconds = current_time.second
                now_seconds = hours * 3600 + minutes * 60 + seconds
                # print("s", wt.start_time_sec)
                # print("n", now_seconds)
                # print("e", wt.end_time_sec)

                if wt.start_time_sec <= now_seconds and now_seconds <= wt.end_time_sec:
                    print(f'[{account.credentials.email}] попытка обновления токена доступа...')
                    account.oauth = await glovo.refresh()
                    accounts_controller.update_account(account)
                    attempt = 1
                    return await worker(http_client, account, accounts_controller, attempt, successful_h, unsuccessful_h, all_hours)

    except JSONDecodeError:
        return print(f'[{account.credentials.email}] Завершили работу аккаунта: необходимо удалить бракованный прокси')

    fake_slots, error_slots = [], []

    successful_slots = []

    cloned_worktimes = []
    cloned_worktimes.extend(account.settings.worktimes)
    workedwts = []
    # monday = []
    # tuesday = []
    # wednesday = []
    # thursday = []
    # friday = []
    # sunday = []
    # saturday = []
    # all_days = ""
    while True:
        now = datetime.now()
        hours_in_seconds = now.hour * 3600
        minutes_in_seconds = now.minute * 60
        current_sec = hours_in_seconds + minutes_in_seconds

        await asyncio.sleep(.1)

        if not account.settings.worktimes:
            account.settings.worktimes.extend(cloned_worktimes)
            workedwts = []

        for wt in account.settings.worktimes:
            if current_sec < wt.end_time_sec:
                if (current_sec >= wt.start_time_sec) and (current_sec <= wt.end_time_sec):
                    if wt not in workedwts:
                        workedwts.append(wt)
                    break
            else:
                if wt in workedwts:
                    account.settings.worktimes.remove(wt)
                    for i in desired_slots:
                        slot = (i.end_ts - i.start_ts) / 3600 / 1000
                        all_hours += slot
                    text = f'''<b>{account.credentials.email}</b>\nУспешно взято часов: <code>{successful_h}</code> 
                    ч.\nНе удалось взять: <code>{unsuccessful_h}</code> ч.\nВсего часов: <code>{all_hours}</code> ч. '''
                    async with AsyncClient() as cl:
                        await cl.post(
                            f'https://api.telegram.org/bot{bot_token}/sendMessage',
                            data={'chat_id': account.filter.chat_id_1, 'text': text, 'parse_mode': 'HTML'}
                        )
                        await cl.post(
                            f'https://api.telegram.org/bot{bot_token}/sendMessage',
                            data={'chat_id': account.filter.chat_id_2, 'text': text, 'parse_mode': 'HTML'}
                        )
        else:
            continue
        try:
            free_slots = await glovo.get_free_slots()

            if not desired_slots:
                text = f'''<b>{account.credentials.email}</b>\nЗавершено\n\nУспешно взято часов: <code>{successful_h}</code> ч.\nНе удалось взять: <code>{unsuccessful_h}</code> ч.\nВсего часов: <code>{all_hours}</code> ч.'''
                async with AsyncClient() as cl:
                    await cl.post(
                        f'https://api.telegram.org/bot{bot_token}/sendMessage',
                        data={'chat_id': account.filter.chat_id_1, 'text': text, 'parse_mode': 'HTML'}
                    )
                    await cl.post(
                        f'https://api.telegram.org/bot{bot_token}/sendMessage',
                        data={'chat_id': account.filter.chat_id_2, 'text': text, 'parse_mode': 'HTML'}
                    )

                return print(f'[{account.credentials.email}] Завершили работу аккаунта')
                # return await worker(http_client, account, accounts_controller, attempt)

            for free_slot in free_slots:
                for desired_slot in desired_slots:
                    if account.filter.zone == "Poland":
                        if datetime.now().replace(tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0,
                                                                                        microsecond=0) - timedelta(
                            hours=1) <= (
                                datetime.fromtimestamp(desired_slot.start_ts // 1000,
                                                       timezone('Etc/GMT-0'))) < datetime.now().replace(
                            tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0, microsecond=0):
                            desired_slots.remove(desired_slot)
                            continue
                    if account.filter.zone == "Ukraine":
                        if datetime.now().replace(tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0,
                                                                                        microsecond=0) <= (
                                datetime.fromtimestamp(desired_slot.start_ts // 1000,
                                                       timezone('Etc/GMT-0'))) < datetime.now().replace(
                            tzinfo=timezone('Etc/GMT-0')).replace(minute=0, second=0,
                                                                  microsecond=0) + timedelta(hours=1):
                            desired_slots.remove(desired_slot)
                            continue
                        # if datetime.now().replace(tzinfo=timezone('Etc/GMT-0')).replace(hour=21, minute=0, second=0,
                        #                                                                 microsecond=0) <= (
                        #         datetime.fromtimestamp(desired_slot.start_ts // 1000,
                        #                                timezone('Etc/GMT-0'))) < datetime.now().replace(
                        #     tzinfo=timezone('Etc/GMT-0')).replace(hour=21, minute=0, second=0,
                        #                                           microsecond=0) + timedelta(hours=1):
                        #     print(datetime.now().replace(tzinfo=timezone('Etc/GMT-0')).replace(hour=21, minute=0,
                        #                                                                        second=0,
                        #                                                                        microsecond=0))
                        #     desired_slots.remove(desired_slot)
                        #     print(desired_slots)
                        #     continue
                    if (free_slot.start_ts == desired_slot.start_ts) and (free_slot.end_ts == desired_slot.end_ts):
                        for fake_slot_id, ban_ts in fake_slots:
                            if (int(time.time()) - ban_ts) >= 3600:
                                sdt = datetime.fromtimestamp(free_slot.start_ts // 1000, timezone('Etc/GMT-0'))
                                edt = datetime.fromtimestamp(free_slot.end_ts // 1000, timezone('Etc/GMT-0'))
                                srt_t = f'{sdt.hour:02d}:{sdt.minute:02d}-{edt.hour:02d}:{edt.minute:02d}'

                                print(f'[{account.credentials.email}] Убрали фейк слот из исключений: {srt_t}')
                                fake_slots.remove([fake_slot_id, ban_ts])

                        if any(free_slot.id in sublist for sublist in fake_slots):
                            break

                        try:
                            status = await glovo.book_slot(free_slot.id)

                            if status:
                                sdt = datetime.fromtimestamp(free_slot.start_ts // 1000, timezone('Etc/GMT-0'))
                                edt = datetime.fromtimestamp(free_slot.end_ts // 1000, timezone('Etc/GMT-0'))
                                srt_t = f'{sdt.hour:02d}:{sdt.minute:02d}-{edt.hour:02d}:{edt.minute:02d}'
                                print(
                                    f'[{account.credentials.email}] Успешно словили слот: {desired_slot.weekday} {srt_t}')
                                desired_slots.remove(desired_slot)
                                if account.filter.messages_sending_1 == "yes":
                                    send_to_telegram(
                                        f'[{account.credentials.email}] Успешно словили слот: {desired_slot.weekday} {srt_t}',
                                        account.filter.chat_id_1)
                                if account.filter.messages_sending_2 == "yes":
                                    send_to_telegram(
                                        f'[{account.credentials.email}] Успешно словили слот: {desired_slot.weekday} {srt_t}',
                                        account.filter.chat_id_2)
                                if successful_slots and successful_slots[-1].startswith(desired_slot.weekday) and \
                                        successful_slots[-1].endswith(f"{sdt.hour:02d}:{sdt.minute:02d};"):
                                    new = successful_slots[-1].replace(successful_slots[-1][-6:-1],
                                                                       f"{edt.hour:02d}:{edt.minute:02d}")
                                    successful_slots[-1] = new
                                else:
                                    successful_slots.append(f"{desired_slot.weekday} - {srt_t};")
                            successful_h += round(((free_slot.end_ts - free_slot.start_ts) / 3600) / 1000, 1)

                        except (GlovoError, SlotTakeError) as error:
                            unsuccessful_h += round(((free_slot.end_ts - free_slot.start_ts) / 3600) / 1000, 1)
                            error_slots.append(free_slot.id)

                            if error_slots.count(free_slot.id) == 3:
                                sdt = datetime.fromtimestamp(free_slot.start_ts // 1000, timezone('Etc/GMT-0'))
                                edt = datetime.fromtimestamp(free_slot.end_ts // 1000, timezone('Etc/GMT-0'))
                                srt_t = f'{sdt.hour:02d}:{sdt.minute:02d}-{edt.hour:02d}:{edt.minute:02d}'

                                print(f'[{account.credentials.email}] Добавили фейк слот в исключение: {srt_t}')
                                fake_slots.append([free_slot.id, int(time.time())])
                                while free_slot.id in error_slots:
                                    error_slots.remove(free_slot.id)
                            else:
                                sdt = datetime.fromtimestamp(free_slot.start_ts // 1000, timezone('Etc/GMT-0'))
                                edt = datetime.fromtimestamp(free_slot.end_ts // 1000, timezone('Etc/GMT-0'))
                                srt_t = f'{sdt.hour:02d}:{sdt.minute:02d}-{edt.hour:02d}:{edt.minute:02d}'

                                print(
                                    f'[{account.credentials.email}] Не удалось забрать слот ({srt_t}): {error.message}')
                        except AccessTokenError:
                            print(f'[{account.credentials.email}] Обновление токена доступа...')
                            account.oauth = await glovo.refresh()
                            accounts_controller.update_account(account)
                        except RequestError:
                            print(f'[{account.credentials.email}] Ошибка подключения')
                        except JSONDecodeError:
                            print(f'[{account.credentials.email}] Запрос вернул неизвестные данные')
                        except AccountBlocked as error:
                            send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.',
                                             account.filter.chat_id_1)
                            send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.',
                                             account.filter.chat_id_2)
                            print(f'[{account.credentials.email}] {error.message} Аккаунт заблокирован.')
                        break

        except GlovoError as error:
            print(f'[{account.credentials.email}] Ошибка: {error.message}. Сон на 15 минут')
            await asyncio.sleep(300)
        except AccessTokenError:
            print(f'[{account.credentials.email}] Обновление токена доступа')
            account.oauth = await glovo.refresh()
            accounts_controller.update_account(account)
            return await worker(http_client, account, accounts_controller, attempt, successful_h, unsuccessful_h, all_hours)
        except RequestError:
            print(f'[{account.credentials.email}] Ошибка подключения')
        except JSONDecodeError:
            print(f'[{account.credentials.email}] Запрос вернул неизвестные данные. Отдыхаем 5 минут')
            await asyncio.sleep(300)

        except AccountBlocked as error:
            if block_count == 0:
                send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.', account.filter.chat_id_1)
                send_to_telegram(f'[{account.credentials.email}] Аккаунт заблокирован.', account.filter.chat_id_2)
                print(f'[{account.credentials.email}] {error.message} Аккаунт заблокирован.')
                block_count += 1
        hours = 0
        for i in desired_slots:
            slot = (i.end_ts - i.start_ts) / 3600 / 1000
            hours += slot
        all_hours = hours
        print(
            f'[{account.credentials.email}] Взятых часов: {successful_h} | Не взятых часов: {unsuccessful_h} | Всего '
            f'часов: {all_hours} | Фейк слотов: {len(fake_slots)}')
        # print(successful_slots)
        # for i in successful_slots:
        #     if i.startswith("Понедельник"):
        #         if monday and int(i[-12:-10]) > int(monday[-1][-6:-4]):
        #             monday.append(i)
        #         else:
        #             monday.insert(0, i)
        #     elif i.startswith("Вторник"):
        #         if tuesday and int(i[-12:-10]) > int(tuesday[-1][-6:-4]):
        #             tuesday.append(i)
        #         else:
        #             tuesday.insert(0, i)
        #     elif i.startswith("Среда"):
        #         if wednesday and int(i[-12:-10]) > int(wednesday[-1][-6:-4]):
        #             wednesday.append(i)
        #         else:
        #             wednesday.insert(0, i)
        #     elif i.startswith("Четверг"):
        #         if thursday and int(i[-12:-10]) > int(thursday[-1][-6:-4]):
        #             thursday.append(i)
        #         else:
        #             thursday.insert(0, i)
        #     elif i.startswith("Пятница"):
        #         if friday and int(i[-12:-10]) > int(friday[-1][-6:-4]):
        #             friday.append(i)
        #         else:
        #             friday.insert(0, i)
        #     elif i.startswith("Суббота"):
        #         if sunday and int(i[-12:-10]) > int(sunday[-1][-6:-4]):
        #             sunday.append(i)
        #         else:
        #             sunday.insert(0, i)
        #     elif i.startswith("Воскресенье"):
        #         if saturday and int(i[-12:-10]) > int(saturday[-1][-6:-4]):
        #             saturday.append(i)
        #         else:
        #             saturday.insert(0, i)
        #
        # all_days += " ".join(monday)
        # all_days += " ".join(tuesday)
        # all_days += " ".join(wednesday)
        # all_days += " ".join(thursday)
        # all_days += " ".join(friday)
        # all_days += " ".join(sunday)
        # all_days += " ".join(saturday)
        # mid_days = all_days.replace(" ", "")
        # finely = mid_days.replace(";", "; ")

        atexit_1.register(idname, send_to_telegram,
                        f'<b>{account.credentials.email}</b>\nЗавершено\n\nУспешно взято часов: <code>{successful_h}</code> ч.\n{successful_slots}\nНе удалось взять: <code>{unsuccessful_h}</code> ч.\nВсего часов: <code>{all_hours}</code> ч.',
                        account.filter.chat_id_1)
        atexit_2.register(idname, send_to_telegram,
                          f'<b>{account.credentials.email}</b>\nЗавершено\n\nУспешно взято часов: <code>{successful_h}</code> ч.\n{successful_slots}\nНе удалось взять: <code>{unsuccessful_h}</code> ч.\nВсего часов: <code>{all_hours}</code> ч.',
                          account.filter.chat_id_2)
        await asyncio.sleep(account.settings.actions_timeout + random.uniform(*account.settings.random_timeout))


if __name__ == '__main__':
    try:
        # loop = asyncio.get_event_loop()
        # loop.run_until_complete(main())
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except Exception as error:
        print(f'\nПрограмма завершила свою работу с ошибкой: {error}')
    except KeyboardInterrupt:
        print(f'\nВы завершили работу программы. Отправка уведомлений')
        atexit_1.notify()
        atexit_2.notify()
    finally:
        sys.exit()
