import os
import sys
import logging
import traceback
import telebot
import gspread
from google.oauth2.service_account import Credentials
from telebot import types
from datetime import datetime
import re
import html
import math

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)


# Декоратор для обработки ошибок Google API
def handle_google_api_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Google API Error in {func.__name__}: {str(e)}"
            logging.error(error_msg)

            # Если это ошибка 429 (лимит запросов), ждем
            if "429" in str(e) or "quota" in str(e).lower():
                logging.info("Превышен лимит запросов. Ждем 60 секунд...")
                import time
                time.sleep(60)

            # Пробуем выполнить функцию снова
            try:
                return func(*args, **kwargs)
            except:
                raise

    return wrapper


TOKEN = "7568162485:AAFR6H3KwBUTwH_Nkq5SkhtkXCcggT8pynA"
bot = telebot.TeleBot(TOKEN)

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive',
         'https://www.googleapis.com/auth/spreadsheets']

creds = Credentials.from_service_account_file('inventorybot-452710-eb3246fd7e0d.json', scopes=scope)
client = gspread.authorize(creds)

sheet = client.open("Инвентаризация для бота").sheet1

SPREADSHEET_ID = "1--jB0l8igPkwTJeJk-4-K8Ted4--o4lf2iualyB-wM8"

selected_column = None

# Переменные для управления состоянием
user_states = {}

# Константы столбцов (после удаления столбца B)
COL_NAME = 1  # A - Название позиции
COL_DESCRIPTION = 2  # B - Описание (бывший C)
COL_NON_CRIT = 3  # C - Не крит (бывший D)
COL_CRIT = 4  # D - Крит (бывший E)
COL_FIRST_INVENT = 5  # E - Первый столбец с инвентаризацией (бывший F)


def format_cell(cell_range, color):
    sheet.format(
        cell_range,
        {
            "backgroundColor": color,
            "horizontalAlignment": "CENTER",
        }
    )


def format_column_white(column_index):
    """Форматирует весь столбец в белый цвет"""
    try:
        column_range = f"{gspread.utils.rowcol_to_a1(1, column_index)}:{gspread.utils.rowcol_to_a1(200, column_index)}"
        sheet.format(column_range, {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1}
        })
    except Exception as e:
        logging.error(f"Ошибка при форматировании столбца {column_index} в белый: {e}")


def align_column_center(column):
    try:
        column_range = gspread.utils.rowcol_to_a1(4, column) + ":" + gspread.utils.rowcol_to_a1(114, column)
        sheet.format(
            column_range,
            {
                "horizontalAlignment": "CENTER",
            }
        )
    except Exception as e:
        print(f"Ошибка при выравнивании столбца: {e}")


def extract_number(value):
    if value is None:
        return None

    value_str = str(value).strip().lower()

    # Обработка значения "inf"
    if value_str == "inf":
        return float('inf')

    # Обработка значения "-1"
    if value_str == "-1":
        return -1

    # Обработка других числовых значений
    match = re.search(r"(-?\d+(\.\d+)?)", value_str.replace(',', '.'))
    return float(match.group(1)) if match else None


def check_today_date_exists():
    """Проверяет, существует ли сегодняшняя дата в таблице, не создавая ее"""
    try:
        today = datetime.now().strftime("%d.%m.%Y")

        # Получаем все данные первой строки
        try:
            values = sheet.get('A1:ZZ1')
            if values:
                all_row_1 = values[0]
            else:
                all_row_1 = []
        except:
            all_row_1 = sheet.row_values(1)

        # Проверяем, есть ли сегодняшняя дата в первой строке
        if today in all_row_1:
            column_index = all_row_1.index(today) + 1
            return True, column_index, all_row_1
        else:
            return False, None, all_row_1

    except Exception as e:
        logging.error(f"Ошибка при проверке даты: {e}")
        return False, None, []


def find_empty_column_after_last_filled(all_row_1):
    """Находит первый пустой столбец после последнего заполненного"""
    # Находим последний заполненный столбец
    last_filled = 0
    for i, cell in enumerate(all_row_1, start=1):
        if cell and cell != '':
            last_filled = i

    # Определяем сколько столбцов после последнего заполненного
    total_cols = len(all_row_1)
    empty_after = total_cols - last_filled

    # Если после заполненных есть пустые столбцы
    if empty_after > 0:
        # Используем первый пустой столбец ПОСЛЕ заполненных
        return last_filled + 1, total_cols
    else:
        # Если после заполненных нет пустых столбцов
        return total_cols + 1, total_cols


def create_today_date_column():
    """Создает столбец для сегодняшней даты"""
    try:
        today = datetime.now().strftime("%d.%m.%Y")

        # Получаем все данные первой строки
        try:
            values = sheet.get('A1:ZZ1')
            if values:
                all_row_1 = values[0]
            else:
                all_row_1 = []
        except:
            all_row_1 = sheet.row_values(1)

        # Проверяем, существует ли уже сегодняшняя дата
        if today in all_row_1:
            return all_row_1.index(today) + 1, all_row_1

        # Находим место для новой даты
        next_empty_column, total_cols = find_empty_column_after_last_filled(all_row_1)

        # Если нужно добавить столбец
        if next_empty_column > total_cols:
            # Добавляем только один столбец
            sheet.add_cols(1)

        # Форматируем новый столбец в белый цвет
        format_column_white(next_empty_column)

        # Записываем дату
        sheet.update_cell(1, next_empty_column, today)

        # Форматируем ячейку с датой
        format_cell(gspread.utils.rowcol_to_a1(1, next_empty_column), {"red": 1, "green": 1, "blue": 1})

        # Выравниваем весь столбец
        align_column_center(next_empty_column)

        return next_empty_column, all_row_1

    except Exception as e:
        logging.error(f"Ошибка при создании столбца с датой: {e}")
        return None, []


def ask_about_inventory(message):
    """Спрашивает пользователя о начале инвентаризации"""
    try:
        today = datetime.now().strftime("%d.%m.%Y")

        # Проверяем существование даты
        date_exists, column_index, all_row_1 = check_today_date_exists()

        if date_exists:
            # Дата уже существует - сразу продолжаем
            global selected_column
            selected_column = column_index
            bot.send_message(
                message.chat.id,
                f"Инвентаризация за {today} уже существует. Продолжаем заполнение!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            start_inventory(message)
        else:
            # Дата не существует
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            btn_create = types.KeyboardButton("Создать")
            btn_cancel = types.KeyboardButton("Отмена")
            markup.add(btn_create, btn_cancel)

            bot.send_message(
                message.chat.id,
                f"Инвентаризация за {today} ещё не существует. Хотите создать новую инвентаризацию?",
                reply_markup=markup
            )

            # Сохраняем состояние пользователя
            user_states[message.chat.id] = {
                'state': 'ask_create_new'
            }

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")
        show_menu(message)


def process_inventory_response(message):
    """Обрабатывает ответ пользователя о начале инвентаризации"""
    global selected_column

    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})
    current_state = user_state.get('state')

    if message.text == "Отмена":
        if chat_id in user_states:
            del user_states[chat_id]
        show_menu(message)
        return

    # Обрабатываем только создание новой инвентаризации
    if current_state == 'ask_create_new':
        if message.text == "Создать":
            if chat_id in user_states:
                del user_states[chat_id]
            create_and_start_inventory(message)


def create_and_start_inventory(message):
    """Создает новую инвентаризацию и начинает заполнение"""
    global selected_column

    try:
        # Создаем столбец с сегодняшней датой
        column_index, all_row_1 = create_today_date_column()

        if column_index:
            selected_column = column_index
            today = datetime.now().strftime("%d.%m.%Y")
            bot.send_message(
                message.chat.id,
                f"Создана новая инвентаризация за {today}!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            start_inventory(message)
        else:
            bot.send_message(
                message.chat.id,
                "Не удалось создать инвентаризацию. Попробуйте позже.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            show_menu(message)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при создании инвентаризации: {e}")
        show_menu(message)


def manage_column_visibility():
    """Управляет видимостью столбцов: оставляет видимыми столбцы A-D и последние 5 инвентаризаций"""
    try:
        # Получаем все значения первой строки
        try:
            values = sheet.get('A1:ZZ1')
            if values:
                all_row_1 = values[0]
            else:
                all_row_1 = []
        except:
            all_row_1 = sheet.row_values(1)

        # Находим все заполненные столбцы (где есть дата)
        filled_columns = []
        for i, cell in enumerate(all_row_1, start=1):
            if cell and cell != '':
                filled_columns.append(i)

        if len(filled_columns) <= 5:
            return

        # Определяем какие столбцы должны быть видимыми
        visible_columns = list(range(1, 5))  # Столбцы A-D
        last_filled = filled_columns[-5:] if len(filled_columns) >= 5 else filled_columns
        visible_columns.extend(last_filled)
        visible_columns = list(set(visible_columns))

        # Определяем все столбцы которые нужно скрыть
        max_column = max(len(all_row_1), filled_columns[-1] if filled_columns else 4)
        columns_to_hide = []
        for col in range(5, max_column + 1):
            if col not in visible_columns:
                columns_to_hide.append(col)

        if not columns_to_hide:
            return

        # Группируем скрываемые столбцы в диапазоны
        hidden_ranges = []
        start = columns_to_hide[0]
        end = columns_to_hide[0]

        for col in columns_to_hide[1:]:
            if col == end + 1:
                end = col
            else:
                hidden_ranges.append((start, end))
                start = col
                end = col
        hidden_ranges.append((start, end))

        # Создаем запросы на скрытие столбцов
        requests = []
        for start_col, end_col in hidden_ranges:
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": start_col - 1,
                        "endIndex": end_col
                    },
                    "properties": {
                        "hiddenByUser": True
                    },
                    "fields": "hiddenByUser"
                }
            })

        if requests:
            sheet.spreadsheet.batch_update({'requests': requests})

    except Exception as e:
        print(f"Ошибка при управлении видимостью столбцов: {e}")


def show_hidden_columns():
    """Показывает все скрытые столбцы (для отладки или ручного управления)"""
    try:
        # Получаем все значения первой строки
        try:
            values = sheet.get('A1:ZZ1')
            if values:
                all_row_1 = values[0]
            else:
                all_row_1 = []
        except:
            all_row_1 = sheet.row_values(1)

        max_column = len(all_row_1)

        # Создаем запрос на показ всех столбцов
        requests = [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": 4,
                    "endIndex": max_column
                },
                "properties": {
                    "hiddenByUser": False
                },
                "fields": "hiddenByUser"
            }
        }]

        sheet.spreadsheet.batch_update({'requests': requests})

    except Exception as e:
        print(f"Ошибка при показе скрытых столбцов: {e}")


def delete_old_columns():
    """Удаляет старые столбцы, оставляя только последние N инвентаризаций"""
    try:
        # Получаем все значения первой строки
        try:
            values = sheet.get('A1:ZZ1')
            if values:
                all_row_1 = values[0]
            else:
                all_row_1 = []
        except:
            all_row_1 = sheet.row_values(1)

        # Находим все заполненные столбцы (где есть дата)
        filled_columns = []
        for i, cell in enumerate(all_row_1, start=1):
            if cell and cell != '':
                filled_columns.append(i)

        if len(filled_columns) <= 10:
            return

        # Определяем сколько столбцов нужно удалить
        columns_to_keep = 10
        delete_up_to = filled_columns[-columns_to_keep] - 1

        if delete_up_to <= 4:
            return

        # Создаем запрос на удаление столбцов
        requests = [{
            "deleteDimension": {
                "range": {
                    "sheetId": sheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": 4,
                    "endIndex": delete_up_to
                }
            }
        }]

        sheet.spreadsheet.batch_update({'requests': requests})

    except Exception as e:
        print(f"Ошибка при удалении старых столбцов: {e}")


@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}!")
    show_menu(message)


@bot.message_handler(commands=['menu'])
def menu_command(message):
    show_menu(message)


@bot.message_handler(commands=['stop'])
def stop_command(message):
    global selected_column
    selected_column = None
    bot.send_message(message.chat.id, "Заполнение инвентаризации приостановлено, возвращаемся в главное меню...")
    show_menu(message)


def show_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_start_inventory = types.KeyboardButton("Инвента")
    btn_edit = types.KeyboardButton("Редактирование инвентаризации")
    btn_manage_positions = types.KeyboardButton("Добавление, редактирование, удаление позиций таблицы")
    btn_table_link = types.KeyboardButton("Ссылка на таблицу")
    btn_help = types.KeyboardButton("Помощь")
    markup.add(btn_start_inventory, btn_edit, btn_manage_positions, btn_table_link, btn_help)

    bot.send_message(
        message.chat.id,
        "Главное меню \n"
        "Нажмите кнопку <b>'Инвента'</b>, чтобы начать или продолжить инвентаризацию.\n"
        "Нажмите кнопку <b>'Редактирование инвентаризации'</b>, чтобы изменить запись в таблице.\n"
        "Нажмите кнопку <b>'Добавление, редактирование, удаление позиций таблицы'</b>, чтобы управлять позициями.\n"
        "Нажмите кнопку <b>'Ссылка на таблицу'</b>, чтобы получить ссылочку.\n"
        "Нажмите кнопку <b>'Помощь'</b>, если у вас возникли трудности.",
        reply_markup=markup, parse_mode='html'
    )


def start_inventory(message):
    global selected_column

    if not selected_column:
        bot.send_message(message.chat.id, "Столбец для инвентаризации не выбран. Начните сначала.")
        return

    try:
        product_names = sheet.col_values(COL_NAME)[3:]
        last_row = len(product_names) + 3

        all_values = sheet.batch_get([
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])
        current_values = all_values[0] if all_values else []

        empty_row = None
        has_empty_cells = False

        for i in range(4, last_row + 1):
            if i - 4 >= len(current_values) or not current_values[i - 4]:
                empty_row = i
                has_empty_cells = True
                break

        if has_empty_cells and empty_row <= last_row:
            process_product(message, empty_row)
        else:
            bot.send_message(
                message.chat.id,
                "Инвентаризация завершена. Сейчас составлю список заказов."
            )
            generate_order_list(message)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при чтении данных: {e}")


def process_product(message, row):
    global selected_column

    if not selected_column:
        bot.send_message(message.chat.id, "Столбец для инвентаризации еще не выбран. Пожалуйста, начните сначала.")
        return

    try:
        product_name = sheet.cell(row, COL_NAME).value
        prev_column = selected_column - 1 if selected_column > COL_FIRST_INVENT else None
        prev_value = sheet.cell(row, prev_column).value if prev_column else "Нет данных"
        description = sheet.cell(row, COL_DESCRIPTION).value or "Нет описания"

        # Защита от None
        product_name = html.escape(str(product_name) if product_name else "")
        prev_value = html.escape(str(prev_value) if prev_value else "")
        description = html.escape(str(description) if description else "")

        msg = (
            f"Строка: {row}\n"
            f"Наименование: {product_name}\n"
            f"Прошлая инвента: <b>{prev_value}</b>\n"
            f"Описание: {description}"
        )

        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        btn_stop = types.KeyboardButton("Приостановить инвенту")
        markup.add(btn_stop)

        bot.send_message(message.chat.id, msg, parse_mode='html', reply_markup=markup)
        bot.register_next_step_handler(message, handle_user_input, row, product_name)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при обработке продукта: {e}")


def start_editing(message):
    global selected_column

    # Проверяем существование сегодняшней даты
    date_exists, column_index, all_row_1 = check_today_date_exists()

    if date_exists:
        selected_column = column_index
    else:
        bot.send_message(message.chat.id,
                         "Ошибка: сегодняшняя инвентаризация не найдена. Сначала создайте инвентаризацию.")
        show_menu(message)
        return

    if not selected_column:
        bot.send_message(message.chat.id, "Ошибка: столбец для редактирования не найден. Начните сначала.")
        return

    try:
        last_row = len(sheet.col_values(COL_NAME))
        all_values = sheet.batch_get([
            f"A4:A{last_row}",  # Названия продуктов
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])

        product_names = [item[0] for item in all_values[0]]
        current_values = [item[0] if item else "Не заполнено" for item in all_values[1]]

        # Оставляем только заполненные позиции
        filled_positions = []
        for i, (name, value) in enumerate(zip(product_names, current_values), start=4):
            if value != "Не заполнено":
                # Нумерация от 1
                pos_num = i - 3
                filled_positions.append(f"{pos_num}. {name} - {value}")

        if not filled_positions:
            bot.send_message(message.chat.id, "Нет заполненных позиций для редактирования.")
            show_menu(message)
            return

        # Разбиваем список на группы по 20 элементов
        chunk_size = 20
        for i in range(0, len(filled_positions), chunk_size):
            bot.send_message(
                message.chat.id,
                "<b>Список позиций для редактирования:</b>\n" + "\n".join(filled_positions[i:i + chunk_size]),
                parse_mode='html'
            )

        # Добавляем кнопку "Назад"
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        btn_back = types.KeyboardButton("Назад")
        markup.add(btn_back)

        bot.send_message(
            message.chat.id,
            "Для редактирования конкретной записи впишите её номер или название. Чтобы вернуться в меню нажмите или "
            "введите 'Назад'.",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, process_edit_input)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при загрузке данных: {e}")


def process_edit_input(message):
    global selected_column

    if message.text.lower() == "назад":
        show_menu(message)
        return

    try:
        last_row = len(sheet.col_values(COL_NAME))
        all_values = sheet.batch_get([
            f"A4:A{last_row}",  # Названия продуктов
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])

        product_names = [item[0].lower() for item in all_values[0]]
        current_values = [item[0] if item else "Не заполнено" for item in all_values[1]]

        user_input = message.text.strip().lower()

        # Если введён номер строки
        if user_input.isdigit() or (user_input[:-1].isdigit() and user_input[-1] == '.'):
            # Убираем точку если есть
            if user_input[-1] == '.':
                user_input = user_input[:-1]
            pos_num = int(user_input)
            # Преобразуем номер позиции в номер строки
            row_number = pos_num + 3
            if 4 <= row_number <= last_row:
                process_edit_product(message, row_number)
                return

        # Если введено название позиции
        elif user_input in product_names:
            # Находим первое вхождение
            try:
                row_number = product_names.index(user_input) + 4
                process_edit_product(message, row_number)
                return
            except ValueError:
                pass

        bot.send_message(message.chat.id, "Ошибка: введён некорректный номер или название позиции. Попробуйте ещё раз.")
        bot.register_next_step_handler(message, process_edit_input)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при обработке ввода: {e}")


def process_edit_product(message, row):
    global selected_column

    if not selected_column:
        bot.send_message(message.chat.id, "Ошибка: столбец для редактирования не найден.")
        return

    try:
        product_name = sheet.cell(row, COL_NAME).value
        prev_column = selected_column - 1 if selected_column > COL_FIRST_INVENT else None
        prev_value = sheet.cell(row, prev_column).value if prev_column else "Нет данных"
        description = sheet.cell(row, COL_DESCRIPTION).value or "Нет описания"
        current_value = sheet.cell(row, selected_column).value or "Не заполнено"

        msg = (
            f"Строка: {row}\n"
            f"Наименование: {product_name}\n"
            f"Прошлая инвента: <b>{prev_value}</b>\n"
            f"Описание: {description}\n"
            f"Запись в ячейке: <b>{current_value}</b>\n\n"
            f"Введите новое значение для редактирования или нажмите 'Отменить редактирование'."
        )
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отменить редактирование")
        markup.add(btn_cancel)

        bot.send_message(message.chat.id, msg, parse_mode='html', reply_markup=markup)
        bot.register_next_step_handler(message, handle_edit_input, row, product_name)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при загрузке данных: {e}")


def handle_edit_input(message, row, product_name):
    global selected_column

    if message.text == "Отменить редактирование":
        show_menu(message)
        return

    # Обрабатываем новое значение отдельно, не вызывая handle_user_input()
    user_input = message.text.strip()

    try:
        sheet.update_cell(row, selected_column, user_input)
        bot.send_message(message.chat.id, f"Значение '{user_input}' успешно записано для {product_name}.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при записи данных: {e}")
        return

    # После редактирования не начинаем инвентаризацию, а сразу спрашиваем про продолжение
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_yes = types.KeyboardButton("Да")
    btn_no = types.KeyboardButton("Нет")
    markup.add(btn_yes, btn_no)

    bot.send_message(
        message.chat.id,
        "Хотите продолжить редактирование?",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, continue_editing)


def continue_editing(message):
    if message.text == "Да":
        bot.send_message(
            message.chat.id,
            "Для редактирования конкретной записи впишите её номер или название. Чтобы вернуться в меню нажмите или "
            "введите 'Назад'.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(message, process_edit_input)
    else:
        bot.send_message(
            message.chat.id,
            "Редактирование завершено. Возвращаемся в главное меню...",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_menu(message)


def handle_user_input(message, row, product_name):
    global selected_column

    if not selected_column:
        bot.send_message(message.chat.id, "Столбец для инвентаризации еще не выбран. Пожалуйста, начните сначала.")
        return

    user_input = message.text.strip().lower()

    if user_input == "приостановить инвенту":
        stop_command(message)
        return

    if user_input in ["много", "есть", "мало", "стоп"]:
        color = {"red": 0.95, "green": 0.80, "blue": 0.80} if user_input in ["мало", "стоп"] else \
            {"red": 0.85, "green": 0.94, "blue": 0.83}
    else:
        number = extract_number(user_input)
        if number is None:
            bot.send_message(
                message.chat.id,
                "Неправильный формат ввода. Обратите внимание на строку с форматом. Если вам нужно ввести какую-то "
                "команду, то необходимо сначала приостановить инвентаризацию, нажав на соответствующую кнопку или "
                "введя сообщение 'Приостановить инвенту' вручную."
            )
            process_product(message, row)
            return

        non_critical_value = extract_number(sheet.cell(row, COL_NON_CRIT).value)
        critical_value = extract_number(sheet.cell(row, COL_CRIT).value)

        if non_critical_value is not None and critical_value is not None:
            if critical_value < number <= non_critical_value:
                color = {"red": 0.99, "green": 0.95, "blue": 0.80}
            elif number <= critical_value:
                color = {"red": 0.95, "green": 0.80, "blue": 0.80}
            else:
                color = None
        else:
            color = None

    try:
        sheet.update_cell(row, selected_column or 1, user_input)
        if color:
            format_cell(gspread.utils.rowcol_to_a1(row, selected_column or 1), color)

        bot.send_message(message.chat.id, f"Значение '{user_input}' успешно записано для {product_name}.")
        start_inventory(message)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при записи данных: {e}")


def generate_order_list(message):
    global selected_column

    non_critical_items = []
    critical_items = []
    stop_items = []

    try:
        today = datetime.now().strftime("%d.%m.%Y")
        last_row = len(sheet.col_values(COL_NAME))

        all_values = sheet.batch_get([
            f"A4:A{last_row}",
            f"C4:C{last_row}",  # Не критические значения (бывший D)
            f"D4:D{last_row}",  # Критические значения (бывший E)
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])

        product_names = [item[0] for item in all_values[0]]

        # Обрабатываем значения "Не крит" с учетом строки "inf"
        non_critical_values = []
        for item in all_values[1]:
            if item and item[0]:
                val = str(item[0]).strip().lower()
                if val == "inf":
                    non_critical_values.append(float('inf'))
                else:
                    non_critical_values.append(extract_number(item[0]))
            else:
                non_critical_values.append(float('inf'))

        # Обрабатываем значения "Крит" с учетом строки "-1"
        critical_values = []
        for item in all_values[2]:
            if item and item[0]:
                val = str(item[0]).strip()
                if val == "-1":
                    critical_values.append(-1)
                else:
                    critical_values.append(extract_number(item[0]))
            else:
                critical_values.append(-1)

        current_values = [item[0] if item else "" for item in all_values[3]]

        for product_name, non_critical, critical, current in zip(product_names, non_critical_values, critical_values,
                                                                 current_values):
            current = str(current).strip().lower()
            number = extract_number(current)

            if current in ["стоп", "0"]:
                stop_items.append(product_name)
                continue

            if current in ["много", "есть"]:
                continue

            if current == "мало":
                critical_items.append(product_name)
                continue

            if number is not None:
                if critical <= number < non_critical:
                    non_critical_items.append(product_name)
                elif number <= critical:
                    critical_items.append(product_name)

        order_list = f"<b>Инвентаризация за {today}</b>\n\n"

        if non_critical_items:
            order_list += "<b>Не Крит:</b>\n" + "\n".join(non_critical_items) + "\n\n"
        if critical_items:
            order_list += "<b>Крит:</b>\n" + "\n".join(critical_items) + "\n\n"
        if stop_items:
            order_list += "<b>Стоп:</b>\n" + "\n".join(stop_items) + "\n\n"

        order_list += ("<a href='https://docs.google.com/spreadsheets/d/1--jB0l8igPkwTJeJk-4-K8Ted4--o4lf2iualyB-wM8"
                       "/edit?pli=1&gid=0#gid=0'>📋 Открыть таблицу</a>")

        bot.send_message(message.chat.id, order_list, parse_mode="HTML", disable_web_page_preview=True)

        # Управление видимостью столбцов после завершения инвентаризации
        try:
            manage_column_visibility()
        except Exception as e:
            print(f"Ошибка при управлении видимостью: {e}")

        show_menu(message)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при генерации списка заказов: {e}")


# Команды для ручного управления скрытием/показом столбцов
@bot.message_handler(commands=['showcolumns'])
def show_columns_command(message):
    """Команда для показа всех скрытых столбцов"""
    try:
        show_hidden_columns()
        bot.send_message(message.chat.id, "Все скрытые столбцы показаны")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")


@bot.message_handler(commands=['hidecolumns'])
def hide_columns_command(message):
    """Команда для скрытия старых столбцов"""
    try:
        manage_column_visibility()
        bot.send_message(message.chat.id, "Старые столбцы скрыты")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")


@bot.message_handler(commands=['cleanup'])
def cleanup_columns_command(message):
    """Команда для удаления старых столбцов (использовать с осторожностью!)"""
    try:
        delete_old_columns()
        bot.send_message(message.chat.id, "Старые столбцы удалены")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")


@bot.message_handler(commands=['secret'])
def secret_command(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_yes = types.KeyboardButton("Да")
    btn_no = types.KeyboardButton("Нет")
    markup.add(btn_yes, btn_no)

    bot.send_message(
        message.chat.id,
        "Вы Женя Чечёта?!",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, process_secret_response)


def process_secret_response(message):
    if message.text == "Нет":
        bot.send_message(
            message.chat.id,
            "Возвращайтесь, когда станете Чечётой...",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_menu(message)
        return

    # Проверяем, началась ли инвентаризация (установлен ли selected_column)
    if selected_column is None:
        bot.send_message(
            message.chat.id,
            "Ошибка: инвентаризация ещё не начиналась. Запустите её перед использованием этой команды.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_menu(message)
        return

    # Проверяем, завершена ли инвентаризация
    if not is_inventory_complete():
        bot.send_message(
            message.chat.id,
            "Инвентаризация ещё не завершена.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_menu(message)
        return

    # Составляем сообщение с остатками
    try:
        leftovers = get_leftovers()
        bot.send_message(message.chat.id, leftovers, reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при составлении списка остатков: {e}")

    show_menu(message)


def is_inventory_complete():
    """Проверяет, завершена ли инвентаризация."""
    product_names = sheet.col_values(COL_NAME)[3:]
    last_row = len(product_names) + 3

    column_values = sheet.col_values(selected_column)[3:last_row]

    for value in column_values:
        if not value or str(value).strip() == "":
            return False
    return True


def get_leftovers():
    """Получает остатки из таблицы."""

    product_map = {
        "трубочки сгущ": "Трубочки сгущёнка",
        "трубочки крем": "Трубочки крем",
        "эклер": "Эклер",
        "птичье молоко": "Птичье молоко",
        "тирамису": "Десерт тирамису",
        "картошка": "Картошка",
        "бискотти": "Бискотти"
    }

    product_names = sheet.col_values(COL_NAME)[3:]
    last_row = len(product_names) + 3

    all_values = sheet.batch_get([
        f"A4:A{last_row}",
        f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
    ])

    name_column = [item[0] if item else "" for item in all_values[0]]
    value_column = [item[0] if item else "Нет данных" for item in all_values[1]]

    leftovers = []

    for short_name, full_name in product_map.items():
        if full_name in name_column:
            row_index = name_column.index(full_name)
            value = value_column[row_index] if row_index < len(value_column) else "Нет данных"
            leftovers.append(f"• {short_name}: {value}")

    leftovers_text = "\n".join(leftovers)
    return f"Остатки:\n{leftovers_text}"


# =================== НОВАЯ ФУНКЦИОНАЛЬНОСТЬ: УПРАВЛЕНИЕ ПОЗИЦИЯМИ ===================

def start_manage_positions(message):
    """Начало управления позициями"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_yes = types.KeyboardButton("Да")
    btn_no = types.KeyboardButton("Нет")
    markup.add(btn_yes, btn_no)

    bot.send_message(
        message.chat.id,
        "Функция редактирования позиций. С помощью неё вы можете добавлять новые и убирать старые позиции из таблицы инвентаризации. Хотите приступить к редактированию?",
        reply_markup=markup
    )

    user_states[message.chat.id] = {
        'state': 'manage_positions_start'
    }
    bot.register_next_step_handler(message, handle_manage_positions_response)


def handle_manage_positions_response(message):
    """Обработка ответа на начало управления позициями"""
    chat_id = message.chat.id

    if message.text == "Нет":
        if chat_id in user_states:
            del user_states[chat_id]
        show_menu(message)
        return

    if message.text == "Да":
        # Показываем список позиций
        show_positions_list(message)


def show_positions_list(message):
    """Показывает список всех позиций"""
    try:
        # Получаем все названия позиций начиная с 4 строки
        names = sheet.col_values(COL_NAME)[3:]  # Пропускаем первые 3 строки
        descriptions = sheet.col_values(COL_DESCRIPTION)[3:]
        non_crit_values = sheet.col_values(COL_NON_CRIT)[3:]
        crit_values = sheet.col_values(COL_CRIT)[3:]

        # Формируем список позиций
        positions = []
        for i in range(len(names)):
            if names[i]:  # Если есть название
                positions.append(f"{i + 1}. {names[i]}")

        if not positions:
            bot.send_message(message.chat.id, "В таблице нет позиций.")
            if message.chat.id in user_states:
                del user_states[message.chat.id]
            show_menu(message)
            return

        # Разбиваем список на части по 20 позиций
        chunk_size = 20
        for i in range(0, len(positions), chunk_size):
            bot.send_message(
                message.chat.id,
                "<b>Список позиций:</b>\n" + "\n".join(positions[i:i + chunk_size]),
                parse_mode='html'
            )

        # Кнопки для управления
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_add = types.KeyboardButton("Добавить запись")
        btn_back = types.KeyboardButton("Назад")
        markup.add(btn_add, btn_back)

        bot.send_message(
            message.chat.id,
            "Для редактирования или удаления конкретной записи, впишите её номер или название. "
            "Для добавления записи нажмите кнопку 'Добавить запись'. "
            "Чтобы вернуться в меню нажмите или введите 'Назад'.",
            reply_markup=markup
        )

        # Сохраняем данные о позициях в состоянии пользователя
        user_states[message.chat.id] = {
            'state': 'manage_positions_list',
            'positions_data': {
                'names': names,
                'descriptions': descriptions,
                'non_crit': non_crit_values,
                'crit': crit_values
            }
        }

        bot.register_next_step_handler(message, handle_position_selection)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при загрузке списка позиций: {e}")
        if message.chat.id in user_states:
            del user_states[message.chat.id]
        show_menu(message)


def handle_position_selection(message):
    """Обработка выбора позиции"""
    chat_id = message.chat.id

    if message.text == "Назад":
        if chat_id in user_states:
            del user_states[chat_id]
        show_menu(message)
        return

    if message.text == "Добавить запись":
        start_add_position(message)
        return

    user_state = user_states.get(chat_id, {})
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    user_input = message.text.strip().lower()

    # Пытаемся найти позицию по номеру
    selected_index = None
    if user_input.isdigit() or (user_input[:-1].isdigit() and user_input[-1] == '.'):
        # Убираем точку если есть
        if user_input[-1] == '.':
            user_input = user_input[:-1]
        pos_num = int(user_input)
        if 1 <= pos_num <= len(names):
            selected_index = pos_num - 1

    # Если не нашли по номеру, ищем по названию
    if selected_index is None:
        for i, name in enumerate(names):
            if name and name.lower() == user_input:
                selected_index = i
                break

    if selected_index is None:
        bot.send_message(message.chat.id, "Ошибка: позиция не найдена. Попробуйте еще раз.")
        bot.register_next_step_handler(message, handle_position_selection)
        return

    # Сохраняем выбранную позицию
    user_states[chat_id]['selected_position'] = selected_index
    user_states[chat_id]['state'] = 'manage_positions_selected'

    # Показываем информацию о позиции
    show_position_info(message, selected_index)


def show_position_info(message, position_index):
    """Показывает информацию о выбранной позиции"""
    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})
    positions_data = user_state.get('positions_data', {})

    names = positions_data.get('names', [])
    descriptions = positions_data.get('descriptions', [])
    non_crit_values = positions_data.get('non_crit', [])
    crit_values = positions_data.get('crit', [])

    if position_index >= len(names):
        bot.send_message(message.chat.id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]
    description = descriptions[position_index] if position_index < len(descriptions) else ""
    non_crit = non_crit_values[position_index] if position_index < len(non_crit_values) else ""
    crit = crit_values[position_index] if position_index < len(crit_values) else ""

    # Обрабатываем значения с учетом строк "inf" и "-1"
    non_crit_str = str(non_crit).strip().lower() if non_crit else ""
    crit_str = str(crit).strip() if crit else ""

    if non_crit_str == "inf" and crit_str == "-1":
        non_crit_display = "∞ (Не считаем)"
        crit_display = "-1 (Не считаем)"
    else:
        # Для счетных товаров используем extract_number
        non_crit_clean = extract_number(non_crit) if non_crit and non_crit_str != "inf" else None
        crit_clean = extract_number(crit) if crit and crit_str != "-1" else None

        non_crit_display = f"{non_crit_clean}" if non_crit_clean is not None else "Не указано"
        crit_display = f"{crit_clean}" if crit_clean is not None else "Не указано"

    msg = (
        f"<b>Позиция в таблице:</b> {position_index + 1}\n"
        f"<b>Наименование:</b> {name}\n"
        f"<b>Описание:</b> {description or 'Нет описания'}\n"
        f"<b>Значение 'Не крит':</b> {non_crit_display}\n"
        f"<b>Значение 'Крит':</b> {crit_display}"
    )

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_edit = types.KeyboardButton("Редактировать")
    btn_move = types.KeyboardButton("Переместить на другую строку")
    btn_delete = types.KeyboardButton("Удалить")
    btn_back = types.KeyboardButton("Назад")
    markup.add(btn_edit, btn_move, btn_delete, btn_back)

    bot.send_message(message.chat.id, msg, parse_mode='html', reply_markup=markup)
    bot.register_next_step_handler(message, handle_position_action)


def handle_position_action(message):
    """Обработка действий с позицией"""
    chat_id = message.chat.id

    if message.text == "Назад":
        # Возвращаемся к списку позиций
        user_states[chat_id]['state'] = 'manage_positions_list'
        bot.send_message(
            chat_id,
            "Для редактирования или удаления конкретной записи, впишите её номер или название. "
            "Для добавления записи нажмите кнопку 'Добавить запись'. "
            "Чтобы вернуться в меню нажмите или введите 'Назад'.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_positions_list(message)
        return

    user_state = user_states.get(chat_id, {})
    position_index = user_state.get('selected_position')

    if message.text == "Редактировать":
        start_edit_position_details(message, position_index)
    elif message.text == "Переместить на другую строку":
        ask_move_position(message, position_index)
    elif message.text == "Удалить":
        confirm_delete_position(message, position_index)
    else:
        bot.send_message(chat_id, "Пожалуйста, выберите действие из предложенных кнопок.")
        bot.register_next_step_handler(message, handle_position_action)


def start_edit_position_details(message, position_index):
    """Начинает редактирование деталей позиции"""
    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    if position_index >= len(names):
        bot.send_message(chat_id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_name = types.KeyboardButton("Наименование")
    btn_desc = types.KeyboardButton("Описание")
    btn_values = types.KeyboardButton("Значение 'Не крит' и 'Крит'")
    btn_back = types.KeyboardButton("Назад")
    markup.add(btn_name, btn_desc, btn_values, btn_back)

    bot.send_message(
        chat_id,
        f"Что вы хотите отредактировать для позиции '{name}'?",
        reply_markup=markup
    )

    user_states[chat_id]['state'] = 'manage_positions_edit_choice'
    user_states[chat_id]['edit_position_index'] = position_index
    bot.register_next_step_handler(message, handle_edit_choice)


def handle_edit_choice(message):
    """Обработка выбора что редактировать"""
    chat_id = message.chat.id

    if message.text == "Назад":
        # Возвращаемся к информации о позиции
        position_index = user_states[chat_id].get('edit_position_index')
        show_position_info(message, position_index)
        return

    user_state = user_states.get(chat_id, {})
    position_index = user_state.get('edit_position_index')
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    if position_index >= len(names):
        bot.send_message(chat_id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]

    if message.text == "Наименование":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        bot.send_message(
            chat_id,
            f"Введите новое наименование для позиции '{name}'\n"
            f"Пример оформления: Стаканы 0.3\n\n"
            f"Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )
        user_states[chat_id]['state'] = 'manage_positions_edit_name'
        bot.register_next_step_handler(message, handle_edit_name, position_index)

    elif message.text == "Описание":
        # Определяем тип позиции для примера
        non_crit = extract_number(positions_data.get('non_crit', [])[position_index]) if position_index < len(
            positions_data.get('non_crit', [])) else None
        crit = extract_number(positions_data.get('crit', [])[position_index]) if position_index < len(
            positions_data.get('crit', [])) else None

        if non_crit == float('inf') and crit == -1:
            example = 'Смотрим наличие. Формат строгий: "есть", "стоп", "мало".'
        else:
            example = 'Считаем количество апельсинов в холодильнике. Формат: 0,5 шт., 3 шт., "стоп".'

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        bot.send_message(
            chat_id,
            f"Введите новое описание для позиции '{name}'\n"
            f"Пример оформления: {example}\n"
            f"Просьба не забывать описывать формат!\n\n"
            f"Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )
        user_states[chat_id]['state'] = 'manage_positions_edit_description'
        bot.register_next_step_handler(message, handle_edit_description, position_index)

    elif message.text == "Значение 'Не крит' и 'Крит'":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_count = types.KeyboardButton("Считаем")
        btn_not_count = types.KeyboardButton("Можем не считать")
        btn_back = types.KeyboardButton("Назад")
        markup.add(btn_count, btn_not_count, btn_back)

        bot.send_message(
            chat_id,
            f"Мы считаем/взвешиваем позицию '{name}', как например, молоко или апельсины, "
            f"или нам это делать не обязательно, как, например, с трубочками для кофе?",
            reply_markup=markup
        )
        user_states[chat_id]['state'] = 'manage_positions_edit_values_type'
        bot.register_next_step_handler(message, handle_edit_values_type, position_index)

    else:
        bot.send_message(chat_id, "Пожалуйста, выберите действие из предложенных кнопок.")
        bot.register_next_step_handler(message, handle_edit_choice)


def handle_edit_name(message, position_index):
    """Обработка редактирования наименования"""
    chat_id = message.chat.id

    if message.text == "Отмена":
        start_edit_position_details(message, position_index)
        return

    new_name = message.text.strip()

    if not new_name:
        bot.send_message(chat_id, "Наименование не может быть пустым. Попробуйте еще раз.")
        bot.register_next_step_handler(message, handle_edit_name, position_index)
        return

    # Обновляем в таблице
    try:
        row = position_index + 4  # +3 для смещения с 0 и +1 потому что строки с 1
        sheet.update_cell(row, COL_NAME, new_name)
        bot.send_message(chat_id, f"Наименование успешно обновлено на '{new_name}'")

        # Обновляем кэш
        if chat_id in user_states and 'positions_data' in user_states[chat_id]:
            user_states[chat_id]['positions_data']['names'][position_index] = new_name

        # Показываем обновленную информацию
        show_position_info(message, position_index)

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении наименования: {e}")
        show_position_info(message, position_index)


def handle_edit_description(message, position_index):
    """Обработка редактирования описания"""
    chat_id = message.chat.id

    if message.text == "Отмена":
        start_edit_position_details(message, position_index)
        return

    new_description = message.text.strip()

    if not new_description:
        bot.send_message(chat_id, "Описание не может быть пустым. Попробуйте еще раз.")
        bot.register_next_step_handler(message, handle_edit_description, position_index)
        return

    # Обновляем в таблице
    try:
        row = position_index + 4
        sheet.update_cell(row, COL_DESCRIPTION, new_description)
        bot.send_message(chat_id, "Описание успешно обновлено")

        # Обновляем кэш
        if chat_id in user_states and 'positions_data' in user_states[chat_id]:
            if position_index < len(user_states[chat_id]['positions_data']['descriptions']):
                user_states[chat_id]['positions_data']['descriptions'][position_index] = new_description

        # Показываем обновленную информацию
        show_position_info(message, position_index)

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении описания: {e}")
        show_position_info(message, position_index)


def handle_edit_values_type(message, position_index):
    """Обработка выбора типа значений"""
    chat_id = message.chat.id

    if message.text == "Назад":
        start_edit_position_details(message, position_index)
        return

    user_state = user_states.get(chat_id, {})
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    if position_index >= len(names):
        bot.send_message(chat_id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]

    if message.text == "Можем не считать":
        # Устанавливаем значения для несчетных позиций
        try:
            row = position_index + 4
            sheet.update_cell(row, COL_NON_CRIT, "inf")
            sheet.update_cell(row, COL_CRIT, -1)
            bot.send_message(chat_id, f"Для позиции '{name}' установлены значения для несчетного товара")

            # Обновляем кэш
            if chat_id in user_states and 'positions_data' in user_states[chat_id]:
                if position_index < len(user_states[chat_id]['positions_data']['non_crit']):
                    user_states[chat_id]['positions_data']['non_crit'][position_index] = str(float('inf'))
                if position_index < len(user_states[chat_id]['positions_data']['crit']):
                    user_states[chat_id]['positions_data']['crit'][position_index] = "-1"

            # Показываем обновленную информацию
            show_position_info(message, position_index)

        except Exception as e:
            bot.send_message(chat_id, f"Ошибка при обновлении значений: {e}")
            show_position_info(message, position_index)

    elif message.text == "Считаем":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        bot.send_message(
            chat_id,
            f"Введите значение 'Не крит' для позиции '{name}'\n"
            f"Формат: '24 л.', '234,8 гр.', '6 рук.'\n"
            f"Это число, с которого позиция будет записываться в не крит.\n\n"
            f"Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )
        user_states[chat_id]['state'] = 'manage_positions_edit_non_crit'
        user_states[chat_id]['edit_position_index'] = position_index
        bot.register_next_step_handler(message, handle_edit_non_crit, position_index)


def handle_edit_non_crit(message, position_index):
    """Обработка редактирования значения 'Не крит'"""
    chat_id = message.chat.id

    if message.text == "Отмена":
        start_edit_position_details(message, position_index)
        return

    user_input = message.text.strip()

    # Извлекаем число из ввода
    number = extract_number(user_input)

    if number is None:
        bot.send_message(
            chat_id,
            "Неправильный формат. Пожалуйста, введите число с единицами измерения, например '24 л.' или '234,8 гр.'"
        )
        bot.register_next_step_handler(message, handle_edit_non_crit, position_index)
        return

    # Сохраняем значение
    user_states[chat_id]['edit_non_crit_value'] = user_input

    user_state = user_states.get(chat_id, {})
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    if position_index >= len(names):
        bot.send_message(chat_id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_cancel = types.KeyboardButton("Отмена")
    markup.add(btn_cancel)

    bot.send_message(
        chat_id,
        f"Введите значение 'Крит' для позиции '{name}'\n"
        f"Формат: '24 л.', '234,8 гр.', '6 рук.'\n"
        f"Это число, с которого позиция будет записываться в крит.\n\n"
        f"Или нажмите 'Отмена' для возврата.",
        reply_markup=markup
    )
    user_states[chat_id]['state'] = 'manage_positions_edit_crit'
    bot.register_next_step_handler(message, handle_edit_crit, position_index)


def handle_edit_crit(message, position_index):
    """Обработка редактирования значения 'Крит'"""
    chat_id = message.chat.id

    if message.text == "Отмена":
        start_edit_position_details(message, position_index)
        return

    user_input = message.text.strip()

    # Извлекаем число из ввода
    number = extract_number(user_input)

    if number is None:
        bot.send_message(
            chat_id,
            "Неправильный формат. Пожалуйста, введите число с единицами измерения, например '24 л.' или '234,8 гр.'"
        )
        bot.register_next_step_handler(message, handle_edit_crit, position_index)
        return

    # Получаем сохраненное значение 'Не крит'
    non_crit_value = user_states[chat_id].get('edit_non_crit_value')

    # Обновляем в таблице
    try:
        row = position_index + 4
        sheet.update_cell(row, COL_NON_CRIT, non_crit_value)
        sheet.update_cell(row, COL_CRIT, user_input)
        bot.send_message(chat_id, "Значения 'Не крит' и 'Крит' успешно обновлены")

        # Обновляем кэш
        if chat_id in user_states and 'positions_data' in user_states[chat_id]:
            if position_index < len(user_states[chat_id]['positions_data']['non_crit']):
                user_states[chat_id]['positions_data']['non_crit'][position_index] = non_crit_value
            if position_index < len(user_states[chat_id]['positions_data']['crit']):
                user_states[chat_id]['positions_data']['crit'][position_index] = user_input

        # Показываем обновленную информацию
        show_position_info(message, position_index)

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении значений: {e}")
        show_position_info(message, position_index)


def ask_move_position(message, position_index):
    """Запрос на перемещение позиции"""
    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    if position_index >= len(names):
        bot.send_message(chat_id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_cancel = types.KeyboardButton("Отмена")
    markup.add(btn_cancel)

    bot.send_message(
        chat_id,
        f"Напишите, на какую позицию (номер) переместить '{name}'\n"
        f"Текущая позиция: {position_index + 1}\n\n"
        f"Или нажмите 'Отмена' для возврата.",
        reply_markup=markup
    )

    user_states[chat_id]['state'] = 'manage_positions_move'
    user_states[chat_id]['move_position_index'] = position_index
    bot.register_next_step_handler(message, handle_move_position)


def handle_move_position(message):
    """Обработка перемещения позиции"""
    chat_id = message.chat.id
    user_input = message.text.strip()

    if user_input == "Отмена":
        position_index = user_states[chat_id].get('move_position_index')
        show_position_info(message, position_index)
        return

    if not user_input.isdigit():
        bot.send_message(chat_id, "Пожалуйста, введите номер позиции (число).")
        bot.register_next_step_handler(message, handle_move_position)
        return

    new_position = int(user_input)
    if new_position < 1:
        bot.send_message(chat_id, "Номер позиции должен быть положительным числом.")
        bot.register_next_step_handler(message, handle_move_position)
        return

    user_state = user_states.get(chat_id, {})
    position_index = user_state.get('move_position_index')
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    if position_index >= len(names):
        bot.send_message(chat_id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]

    # Проверяем, не пытаемся ли переместить на ту же позицию
    if new_position == position_index + 1:
        bot.send_message(chat_id, "Позиция уже находится на этой строке.")
        show_position_info(message, position_index)
        return

    # Исправлено: правильно вычисляем новую строку
    # Если перемещаем позицию вверх (new_position < position_index + 1)
    if new_position < position_index + 1:
        # При перемещении вверх, сначала удаляем, потом вставляем
        target_row = new_position + 3  # Новая позиция в таблице
    else:
        # При перемещении вниз, сначала удаляем, потом вставляем на одну строку выше
        # потому что после удаления строки все строки ниже смещаются вверх
        target_row = new_position + 3  # Желаемая новая позиция
        # Если перемещаем вниз, то после удаления текущей строки, все строки ниже сместятся вверх на 1
        # Поэтому нужно уменьшить target_row на 1
        if new_position > position_index + 1:
            target_row -= 1

    try:
        # Получаем данные текущей строки
        current_row = position_index + 4
        name_value = sheet.cell(current_row, COL_NAME).value
        desc_value = sheet.cell(current_row, COL_DESCRIPTION).value
        non_crit_value = sheet.cell(current_row, COL_NON_CRIT).value
        crit_value = sheet.cell(current_row, COL_CRIT).value

        if str(non_crit_value).strip().lower() == "inf":
            non_crit_value = "inf"

        # Удаляем текущую строку
        sheet.delete_rows(current_row, current_row)

        # Вставляем новую строку
        sheet.insert_row([name_value, desc_value, non_crit_value, crit_value], target_row)

        # Очищаем форматирование всей строки (A-D)
        row_range = f"A{target_row}:D{target_row}"
        sheet.format(row_range, {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1},
            "horizontalAlignment": "LEFT"
        })

        bot.send_message(
            chat_id,
            f"Произошёл перенос позиции '{name}' на позицию номер {new_position}"
        )

        # Обновляем список позиций
        show_positions_list(message)

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при перемещении позиции: {e}")
        show_position_info(message, position_index)


def confirm_delete_position(message, position_index):
    """Подтверждение удаления позиции"""
    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})
    positions_data = user_state.get('positions_data', {})
    names = positions_data.get('names', [])

    if position_index >= len(names):
        bot.send_message(chat_id, "Ошибка: позиция не найдена.")
        show_positions_list(message)
        return

    name = names[position_index]

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_yes = types.KeyboardButton("Да")
    btn_no = types.KeyboardButton("Нет")
    markup.add(btn_yes, btn_no)

    bot.send_message(
        chat_id,
        f"Вы точно хотите удалить позицию '{name}'?",
        reply_markup=markup
    )

    user_states[chat_id]['state'] = 'manage_positions_delete_confirm'
    user_states[chat_id]['delete_position_index'] = position_index
    bot.register_next_step_handler(message, handle_delete_position)


def handle_delete_position(message):
    """Обработка удаления позиции"""
    chat_id = message.chat.id

    if message.text == "Нет":
        position_index = user_states[chat_id].get('delete_position_index')
        show_position_info(message, position_index)
        return

    if message.text == "Да":
        position_index = user_states[chat_id].get('delete_position_index')
        user_state = user_states.get(chat_id, {})
        positions_data = user_state.get('positions_data', {})
        names = positions_data.get('names', [])

        if position_index >= len(names):
            bot.send_message(chat_id, "Ошибка: позиция не найдена.")
            show_positions_list(message)
            return

        name = names[position_index]

        try:
            bot.send_message(chat_id, "Удаление позиции...")

            # Удаляем строку
            row = position_index + 4
            sheet.delete_rows(row, row)  # Исправлено на delete_rows

            bot.send_message(chat_id, "Позиция удалена!")

            # Обновляем список позиций
            show_positions_list(message)

        except Exception as e:
            bot.send_message(chat_id, f"Ошибка при удалении позиции: {e}")
            show_position_info(message, position_index)


def start_add_position(message):
    """Начало добавления новой позиции"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_yes = types.KeyboardButton("Да")
    btn_no = types.KeyboardButton("Нет")
    markup.add(btn_yes, btn_no)

    bot.send_message(
        message.chat.id,
        "Вы уверены, что хотите добавить строчку с новой записью в таблицу?",
        reply_markup=markup
    )

    user_states[message.chat.id]['state'] = 'manage_positions_add_confirm'
    bot.register_next_step_handler(message, handle_add_position_confirm)


def handle_add_position_confirm(message):
    """Обработка подтверждения добавления позиции"""
    chat_id = message.chat.id

    if message.text == "Нет":
        # Возвращаемся к списку позиций
        user_states[chat_id]['state'] = 'manage_positions_list'
        show_positions_list(message)
        return

    if message.text == "Да":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        bot.send_message(
            chat_id,
            "Вводим данные для новой позиции!\n\n"
            "Какую строку займёт позиция? Это может сильно повлиять на удобство заполнения, "
            "допустим, новогодние стаканчики лучше располагать в таблице близко к другим стаканам. "
            "Введите тот номер, под которым хотели бы видеть позицию. "
            "Не переживайте, если это посреди списка, остальные позиции подвинутся)\n\n"
            "Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )

        user_states[chat_id]['state'] = 'manage_positions_add_position'
        user_states[chat_id]['new_position_data'] = {}
        bot.register_next_step_handler(message, handle_add_position_step)


def handle_add_position_step(message):
    """Обработка шага добавления позиции"""
    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})
    step_data = user_state.get('new_position_data', {})

    # Проверка на отмену
    if message.text == "Отмена":
        if chat_id in user_states:
            del user_states[chat_id]
        show_menu(message)
        return

    if 'position_number' not in step_data:
        # Шаг 1: Получение номера позиции
        user_input = message.text.strip()

        if not user_input.isdigit():
            bot.send_message(chat_id, "Пожалуйста, введите номер позиции (число).")
            bot.register_next_step_handler(message, handle_add_position_step)
            return

        position_num = int(user_input)
        if position_num < 1:
            bot.send_message(chat_id, "Номер позиции должен быть положительным числом.")
            bot.register_next_step_handler(message, handle_add_position_step)
            return

        step_data['position_number'] = position_num

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        bot.send_message(
            chat_id,
            "Введите наименование новой позиции\n"
            "Пример оформления: Стаканы 0.3\n\n"
            "Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )

        user_states[chat_id]['new_position_data'] = step_data
        bot.register_next_step_handler(message, handle_add_position_step)
        return

    elif 'name' not in step_data:
        # Шаг 2: Получение наименования
        name = message.text.strip()
        if not name:
            bot.send_message(chat_id, "Наименование не может быть пустым. Попробуйте еще раз.")
            bot.register_next_step_handler(message, handle_add_position_step)
            return

        step_data['name'] = name

        # Спрашиваем, считать ли позицию
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_count = types.KeyboardButton("Считаем")
        btn_not_count = types.KeyboardButton("Можем не считать")
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_count, btn_not_count, btn_cancel)

        bot.send_message(
            chat_id,
            f"Мы считаем/взвешиваем позицию '{name}', как например, молоко или апельсины, "
            f"или нам это делать не обязательно, как, например, с трубочками для кофе?\n\n"
            f"Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )

        user_states[chat_id]['new_position_data'] = step_data
        bot.register_next_step_handler(message, handle_add_position_step)
        return

    elif 'count_type' not in step_data:
        # Шаг 3: Определение типа позиции
        if message.text == "Можем не считать":
            step_data['count_type'] = 'not_count'
            step_data['non_crit'] = float('inf')
            step_data['crit'] = -1

            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            btn_cancel = types.KeyboardButton("Отмена")
            markup.add(btn_cancel)

            # Переходим к описанию
            bot.send_message(
                chat_id,
                "Введите описание для новой позиции\n"
                "Пример оформления: Смотрим наличие. Формат строгий: 'есть', 'стоп', 'мало'.\n"
                "Просьба не забывать описывать формат!\n\n"
                "Или нажмите 'Отмена' для возврата.",
                reply_markup=markup
            )

            user_states[chat_id]['new_position_data'] = step_data
            bot.register_next_step_handler(message, handle_add_position_step)

        elif message.text == "Считаем":
            step_data['count_type'] = 'count'

            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            btn_cancel = types.KeyboardButton("Отмена")
            markup.add(btn_cancel)

            bot.send_message(
                chat_id,
                "Введите значение 'Не крит'\n"
                "Формат: '24 л.', '234,8 гр.', '6 рук.'\n"
                "Это число, с которого позиция будет записываться в не крит.\n\n"
                "Или нажмите 'Отмена' для возврата.",
                reply_markup=markup
            )

            user_states[chat_id]['new_position_data'] = step_data
            bot.register_next_step_handler(message, handle_add_position_step)

        elif message.text == "Отмена":
            if chat_id in user_states:
                del user_states[chat_id]
            show_menu(message)
            return

        else:
            bot.send_message(chat_id, "Пожалуйста, выберите один из предложенных вариантов.")
            bot.register_next_step_handler(message, handle_add_position_step)
        return

    elif step_data.get('count_type') == 'count' and 'non_crit' not in step_data:
        # Шаг 4a: Получение значения 'Не крит' для счетных позиций
        user_input = message.text.strip()
        number = extract_number(user_input)

        if number is None:
            bot.send_message(
                chat_id,
                "Неправильный формат. Пожалуйста, введите число с единицами измерения, например '24 л.' или '234,8 гр.'"
            )
            bot.register_next_step_handler(message, handle_add_position_step)
            return

        step_data['non_crit'] = user_input

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        bot.send_message(
            chat_id,
            "Введите значение 'Крит'\n"
            "Формат: '24 л.', '234,8 гр.', '6 рук.'\n"
            "Это число, с которого позиция будет записываться в крит.\n\n"
            "Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )

        user_states[chat_id]['new_position_data'] = step_data
        bot.register_next_step_handler(message, handle_add_position_step)
        return

    elif step_data.get('count_type') == 'count' and 'crit' not in step_data:
        # Шаг 5a: Получение значения 'Крит' для счетных позиций
        user_input = message.text.strip()
        number = extract_number(user_input)

        if number is None:
            bot.send_message(
                chat_id,
                "Неправильный формат. Пожалуйста, введите число с единицами измерения, например '24 л.' или '234,8 гр.'"
            )
            bot.register_next_step_handler(message, handle_add_position_step)
            return

        step_data['crit'] = user_input

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        # Переходим к описанию
        bot.send_message(
            chat_id,
            "Введите описание для новой позиции\n"
            "Пример оформления: Считаем количество апельсинов в холодильнике. Формат: 0,5 шт., 3 шт., 'стоп'.\n"
            "Просьба не забывать описывать формат!\n\n"
            "Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )

        user_states[chat_id]['new_position_data'] = step_data
        bot.register_next_step_handler(message, handle_add_position_step)
        return

    elif 'description' not in step_data:
        # Шаг 4/6: Получение описания
        description = message.text.strip()
        if not description:
            bot.send_message(chat_id, "Описание не может быть пустым. Попробуйте еще раз.")
            bot.register_next_step_handler(message, handle_add_position_step)
            return

        step_data['description'] = description

        # Показываем сводку
        position_num = step_data['position_number']
        name = step_data['name']
        description = step_data['description']

        if step_data.get('count_type') == 'not_count':
            non_crit_display = "∞ (Не считаем)"
            crit_display = "-1 (Не считаем)"
        else:
            non_crit_display = step_data.get('non_crit', 'Не указано')
            crit_display = step_data.get('crit', 'Не указано')

        msg = (
            f"<b>Позиция в таблице:</b> {position_num}\n"
            f"<b>Наименование:</b> {name}\n"
            f"<b>Описание:</b> {description}\n"
            f"<b>Значение 'Не крит':</b> {non_crit_display}\n"
            f"<b>Значение 'Крит':</b> {crit_display}\n\n"
            f"Проверьте корректность данных. Всё верно?"
        )

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_yes = types.KeyboardButton("Да")
        btn_no = types.KeyboardButton("Нет")
        markup.add(btn_yes, btn_no)

        bot.send_message(chat_id, msg, parse_mode='html', reply_markup=markup)

        user_states[chat_id]['new_position_data'] = step_data
        user_states[chat_id]['state'] = 'manage_positions_add_confirm_final'
        bot.register_next_step_handler(message, handle_add_position_final)
        return


def handle_add_position_final(message):
    """Финальное подтверждение добавления позиции"""
    chat_id = message.chat.id

    if message.text == "Нет":
        # Начинаем заново
        user_states[chat_id]['new_position_data'] = {}
        user_states[chat_id]['state'] = 'manage_positions_add_position'

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_cancel)

        bot.send_message(
            chat_id,
            "Начинаем процесс заполнения заново.\n\n"
            "Какую строку займёт позиция?\n\n"
            "Или нажмите 'Отмена' для возврата.",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, handle_add_position_step)
        return

    if message.text == "Да":
        step_data = user_states[chat_id].get('new_position_data', {})

        position_num = step_data.get('position_number')
        name = step_data.get('name')
        description = step_data.get('description')

        if step_data.get('count_type') == 'not_count':
            non_crit = "inf"
            crit = -1
        else:
            non_crit = step_data.get('non_crit', '')
            crit = step_data.get('crit', '')

        try:
            # Преобразуем номер позиции в номер строки
            target_row = position_num + 3

            # Получаем текущее количество строк
            current_rows = len(sheet.col_values(COL_NAME))

            # Если целевая строка больше текущего количества строк + 3 (первые 3 строки заголовков),
            # то добавляем в конец
            if target_row > current_rows + 1:
                target_row = current_rows + 1

            # Вставляем новую строку
            sheet.insert_row([name, description, non_crit, crit], target_row)

            # Очищаем форматирование всей строки (A-D)
            row_range = f"A{target_row}:D{target_row}"
            sheet.format(row_range, {
                "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                "horizontalAlignment": "LEFT"
            })

            bot.send_message(chat_id, f"Позиция '{name}' успешно добавлена на строку {position_num}")

            # Обновляем список позиций
            show_positions_list(message)

        except Exception as e:
            bot.send_message(chat_id, f"Ошибка при добавлении позиции: {e}")
            show_positions_list(message)


@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    global selected_column

    chat_id = message.chat.id

    # Обработка ответов на вопросы об инвентаризации
    if chat_id in user_states:
        state = user_states[chat_id].get('state', '')

        # Проверяем, не относится ли состояние к управлению инвентаризацией
        if state in ['ask_inventory_type', 'ask_create_new']:
            process_inventory_response(message)
            return

        # Проверяем, не относится ли состояние к управлению позициями
        if state.startswith('manage_positions'):
            # Это состояния управления позициями, их обрабатываем в отдельных функциях
            # Они уже должны быть обработаны через register_next_step_handler
            return

    if message.text == "Инвента":
        ask_about_inventory(message)

    elif message.text == "Редактирование инвентаризации":
        start_editing(message)

    elif message.text == "Добавление, редактирование, удаление позиций таблицы":
        start_manage_positions(message)

    elif message.text == "Ссылка на таблицу":
        bot.send_message(
            message.chat.id,
            "Вот ссылка на таблицу:",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton(
                    "Открыть таблицу",
                    url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
                )
            )
        )

    elif message.text == "Помощь":
        bot.send_message(message.chat.id, "В каждом ПО, предназначенном для эксплуатации пользователями, должна быть "
                                          "техническая поддержка, способная помочь в трудной ситуации. Так вот - "
                                          "здесь такого нет). По всем вопросам лучше лично обратиться к гениальному "
                                          "создателю этого бота.")

    # Старая обработка кнопок "Да"/"Нет" теперь не используется
    elif message.text in ["Да", "Нет"]:
        bot.send_message(
            message.chat.id,
            "Пожалуйста, используйте новые кнопки: 'Продолжить', 'Новая', 'Создать' или 'Отмена'",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_menu(message)


if __name__ == "__main__":
    try:
        # skip_pending=True пропускает накопленные сообщения, чтобы избежать конфликтов
        bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=20)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        # Ждем перед перезапуском
        import time

        time.sleep(5)
