import os
import sys
import requests
import logging
import time

from dotenv import load_dotenv
from logging import StreamHandler
from http import HTTPStatus
from telegram import Bot

from exceptions import SystemVarNameError, NotAvailableAPI


load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ENV_VARS = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/rge'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='bot_logs.log',
    filemode='w',
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)
handler = StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных  окружения."""
    for name_var, var in ENV_VARS.items():
        if not var:
            raise SystemVarNameError(
                f'Отсутствует переменная окружеиня: {name_var}'
            )


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.debug(f'Бот отправил сообщение "{message}"')


def get_api_answer(timestamp):
    """Отправка запроса к ендпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise NotAvailableAPI(f'Ошибка при запросе к API: {error}')
    except Exception as error:
        raise Exception(f'Непредвиденная ошибка: {error}')
    if (response.status_code != HTTPStatus.OK):
        raise NotAvailableAPI(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверка ответа API сервиса на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API не является JSON структурой")
    api_keys = {
        'homeworks': list,
        'current_date': int,
    }
    for key, expected_type in api_keys.items():
        if key not in response.keys():
            raise KeyError(f'Ключ "{key}" отсутствует в ответе API')
        if not isinstance(response[key], expected_type):
            raise TypeError((f'Значение ключа "{key}" из ответа '
                             f'API не является типом {expected_type}'))
    if len(response['homeworks']) > 0:
        if not isinstance(response['homeworks'][0], dict):
            raise TypeError(f'Информация о ДЗ не является типом {dict}')
    else:
        logger.debug('В ответе API отсутствуют новые статусы работ')


def parse_status(homework):
    """Извлечение информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError(
            'Ответ API не содержит информацию об имени домашнего задания'
        )
    status = homework.get('status')
    if status is None:
        raise KeyError(
            'Ответ API не содержит информацию о статусе домашней работы'
        )
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        raise KeyError(
            f'В ответе от API получен неожиданный статус '
            f'домашнего задания - {status}'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():  # noqa: C901
    """Основная логика работы бота."""
    try:
        check_tokens()
        bot = Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
    except SystemVarNameError as error:
        message = (f'Сбой запуска бота: {error}\n'
                   f'Программа принудительно остановлена.')
        logger.critical(message)
    except Exception as error:
        message = f'Сбой в работе программы: {error}'
        logger.critical(message)
    else:
        while True:
            try:
                api_response = get_api_answer(timestamp)
                check_response(api_response)
                homeworks = api_response.get('homeworks')
                timestamp = api_response.get('current_date')
                for hw in homeworks:
                    telegram_message = parse_status(hw)
                    send_message(bot, telegram_message)
            except KeyError as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
            except TypeError as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
            except NotAvailableAPI as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
