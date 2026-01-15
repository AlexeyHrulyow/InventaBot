import os
import sys
import logging
import traceback

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('inventory_bot.log'),
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


import telebot
import gspread
from google.oauth2.service_account import Credentials
from telebot import types
from datetime import datetime
import re

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

RESERVE_COLUMNS_COUNT = 3


def ensure_reserve_columns():
    """Создает резервные столбцы при необходимости"""
    try:
        # Получаем все данные первой строки (достаточно большое количество)
        try:
            values = sheet.get('A1:ZZ1')
            if values:
                all_row_1 = values[0]
            else:
                all_row_1 = []
        except:
            all_row_1 = sheet.row_values(1)

        # Находим последний заполненный столбец
        last_filled = 0
        for i, cell in enumerate(all_row_1, start=1):
            if cell and cell != '':
                last_filled = i

        # Определяем сколько столбцов после последнего заполненного
        total_cols = len(all_row_1)
        empty_after = total_cols - last_filled

        # Если после заполненных меньше 3 пустых столбцов, добавляем недостающие
        if empty_after < RESERVE_COLUMNS_COUNT:
            cols_to_add = RESERVE_COLUMNS_COUNT - empty_after
            sheet.add_cols(cols_to_add)

            # Форматируем добавленные столбцы в белый цвет
            for i in range(cols_to_add):
                col_index = total_cols + i + 1
                format_column_white(col_index)

            return True
        return False
    except Exception as e:
        print(f"Ошибка при создании резервных столбцов: {e}")
        return False


def format_column_white(column_index):
    """Форматирует весь столбец в белый цвет"""
    try:
        # Форматируем диапазон от 1 до 200 строк (можно изменить при необходимости)
        column_range = f"{gspread.utils.rowcol_to_a1(1, column_index)}:{gspread.utils.rowcol_to_a1(200, column_index)}"
        sheet.format(column_range, {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1}
        })
    except Exception as e:
        print(f"Ошибка при форматировании столбца {column_index} в белый: {e}")


def format_cell(cell_range, color):
    sheet.format(
        cell_range,
        {
            "backgroundColor": color,
            "horizontalAlignment": "CENTER",
        }
    )


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
    match = re.search(r"(\d+(\.\d+)?)", str(value).replace(',', '.'))
    return float(match.group(1)) if match else None


def check_and_set_date(message):
    global selected_column

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
            selected_column = all_row_1.index(today) + 1
        else:
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
                next_empty_column = last_filled + 1
            else:
                # Если после заполненных нет пустых столбцов
                # Создаем резервные столбцы
                ensure_reserve_columns()

                # Обновляем данные после создания столбцов
                try:
                    values = sheet.get('A1:ZZ1')
                    if values:
                        all_row_1 = values[0]
                    else:
                        all_row_1 = []
                except:
                    all_row_1 = sheet.row_values(1)

                # Пересчитываем
                last_filled = 0
                for i, cell in enumerate(all_row_1, start=1):
                    if cell and cell != '':
                        last_filled = i

                total_cols = len(all_row_1)
                empty_after = total_cols - last_filled

                # Теперь должен быть хотя бы один пустой столбец
                if empty_after > 0:
                    next_empty_column = last_filled + 1
                else:
                    # На всякий случай, если что-то пошло не так
                    # Создаем один столбец
                    sheet.add_cols(1)
                    next_empty_column = total_cols + 1

            # Записываем дату
            sheet.update_cell(1, next_empty_column, today)

            # Форматируем ячейку с датой
            format_cell(gspread.utils.rowcol_to_a1(1, next_empty_column), {"red": 1, "green": 1, "blue": 1})

            # Выравниваем весь столбец
            align_column_center(next_empty_column)

            selected_column = next_empty_column

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn_yes = types.KeyboardButton("Да")
        btn_no = types.KeyboardButton("Нет")
        markup.add(btn_yes, btn_no)

        bot.send_message(
            message.chat.id,
            f"Инвентаризация {today} {'уже существует' if today in all_row_1 else 'создана'}. Хотите продолжить?",
            reply_markup=markup
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")


def check_and_set_date_silent():
    global selected_column

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

        if today in all_row_1:
            selected_column = all_row_1.index(today) + 1
        else:
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
                next_empty_column = last_filled + 1
            else:
                # Если после заполненных нет пустых столбцов
                # Создаем резервные столбцы
                ensure_reserve_columns()

                # Обновляем данные после создания столбцов
                try:
                    values = sheet.get('A1:ZZ1')
                    if values:
                        all_row_1 = values[0]
                    else:
                        all_row_1 = []
                except:
                    all_row_1 = sheet.row_values(1)

                # Пересчитываем
                last_filled = 0
                for i, cell in enumerate(all_row_1, start=1):
                    if cell and cell != '':
                        last_filled = i

                total_cols = len(all_row_1)
                empty_after = total_cols - last_filled

                if empty_after > 0:
                    next_empty_column = last_filled + 1
                else:
                    sheet.add_cols(1)
                    next_empty_column = total_cols + 1

            # Записываем дату
            sheet.update_cell(1, next_empty_column, today)

            # Форматируем ячейку с датой
            format_cell(gspread.utils.rowcol_to_a1(1, next_empty_column), {"red": 1, "green": 1, "blue": 1})

            # Выравниваем весь столбец
            align_column_center(next_empty_column)

            selected_column = next_empty_column

    except Exception as e:
        print(f"Ошибка при установке даты: {e}")


def manage_column_visibility():
    """Управляет видимостью столбцов: оставляет видимыми столбцы A-E и последние 5 инвентаризаций"""
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

        if len(filled_columns) <= 5:  # Если заполненных столбцов меньше или равно 5, ничего не скрываем
            return

        # Определяем какие столбцы должны быть видимыми
        # Столбцы A-E (1-5) всегда видимы
        # Последние 5 заполненных столбцов тоже видимы
        visible_columns = list(range(1, 6))  # Столбцы A-E

        # Добавляем последние 5 заполненных столбцов
        last_filled = filled_columns[-5:] if len(filled_columns) >= 5 else filled_columns
        visible_columns.extend(last_filled)

        # Убираем дубликаты (на случай если какие-то из последних 5 попадают в A-E)
        visible_columns = list(set(visible_columns))

        # Определяем все столбцы которые нужно скрыть (все остальные)
        # Берем максимальный номер столбца + резервные столбцы
        max_column = max(len(all_row_1), filled_columns[-1] if filled_columns else 5)

        columns_to_hide = []
        for col in range(6, max_column + 1):  # Начинаем с F (6 столбец)
            if col not in visible_columns:
                columns_to_hide.append(col)

        if not columns_to_hide:
            return

        # Группируем скрываемые столбцы в диапазоны для уменьшения количества запросов
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
                        "startIndex": start_col - 1,  # API использует 0-based индексы
                        "endIndex": end_col  # endIndex не включается
                    },
                    "properties": {
                        "hiddenByUser": True
                    },
                    "fields": "hiddenByUser"
                }
            })

        # Выполняем все запросы одним batch_update
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
                    "startIndex": 5,  # Начинаем с F столбца (индекс 5, т.к. 0-based)
                    "endIndex": max_column
                },
                "properties": {
                    "hiddenByUser": False
                },
                "fields": "hiddenByUser"
            }
        }]

        sheet.spreadsheet.batch_update({'requests': requests})
        print("Все столбцы показаны")

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

        if len(filled_columns) <= 10:  # Оставляем последние 10 инвентаризаций + резервные
            return

        # Определяем сколько столбцов нужно удалить (все что до filled_columns[-10])
        columns_to_keep = 10  # Оставляем последние 10 инвентаризаций
        delete_up_to = filled_columns[-columns_to_keep] - 1  # Удаляем все что до этого столбца

        if delete_up_to <= 5:  # Не удаляем столбцы A-E
            return

        # Создаем запрос на удаление столбцов
        requests = [{
            "deleteDimension": {
                "range": {
                    "sheetId": sheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": 5,  # Начинаем с F столбца (после A-E)
                    "endIndex": delete_up_to  # Удаляем до определенного столбца
                }
            }
        }]

        sheet.spreadsheet.batch_update({'requests': requests})
        print(f"Удалены столбцы с F до {gspread.utils.rowcol_to_a1(1, delete_up_to)}")

    except Exception as e:
        print(f"Ошибка при удалении старых столбцов: {e}")


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}!")
    show_menu(message)


@bot.message_handler(commands=['menu'])
def menu(message):
    show_menu(message)


@bot.message_handler(commands=['stop'])
def stop(message):
    global selected_column
    selected_column = None
    bot.send_message(message.chat.id, "Заполнение инвентаризации приостановлено, возвращаемся в главное меню...")
    show_menu(message)


def show_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_start_inventory = types.KeyboardButton("Инвента")
    btn_edit = types.KeyboardButton("Редактировать")  # Новая кнопка
    btn_table_link = types.KeyboardButton("Ссылка на таблицу")
    btn_help = types.KeyboardButton("Помощь")
    markup.add(btn_start_inventory, btn_edit, btn_table_link, btn_help)

    bot.send_message(
        message.chat.id,
        "Главное меню \n"
        "Нажмите кнопку <b>'Инвента'</b>, чтобы начать или продолжить инвентаризацию.\n"
        "Нажмите кнопку <b>'Редактировать'</b>, чтобы изменить запись в таблице.\n"
        "Нажмите кнопку <b>'Ссылка на таблицу'</b>, чтобы получить ссылочку.\n"
        "Нажмите кнопку <b>'Помощь'</b>, если у вас возникли трудности.",
        reply_markup=markup, parse_mode='html'
    )


def show_inventory_keyboard(message):
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_stop = types.KeyboardButton("Приостановить инвенту")
    markup.add(btn_stop)
    bot.send_message(message.chat.id, "Чтобы приостановить инвентаризацию, нажмите или введите 'Приостановить "
                                      "инвентаризацию'.",
                     reply_markup=markup)


def start_inventory(message):
    global selected_column

    if not selected_column:
        bot.send_message(message.chat.id, "Столбец для инвентаризации не выбран. Начните сначала.")
        return

    try:
        product_names = sheet.col_values(1)[3:]  # Читаем названия позиций (столбец A, с 4-й строки)
        last_row = len(product_names) + 3  # Определяем последнюю заполненную строку

        all_values = sheet.batch_get([
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])
        current_values = all_values[0] if all_values else []  # Берём значения из столбца с инвентаризацией

        empty_row = None
        has_empty_cells = False  # Флаг: есть ли незаполненные ячейки

        for i in range(4, last_row + 1):
            if i - 4 >= len(current_values) or not current_values[i - 4]:  # Если ячейка пуста
                empty_row = i
                has_empty_cells = True
                break

        if has_empty_cells and empty_row <= last_row:  # Проверяем, не вылезли ли за пределы таблицы
            process_product(message, empty_row)  # Начинаем заполнение с первой пустой строки
        else:
            bot.send_message(
                message.chat.id,
                "Инвентаризация завершена. Сейчас составлю список заказов."
            )
            generate_order_list(message)  # Завершаем инвентаризацию и создаём список заказов

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при чтении данных: {e}")


import html  # Импортируем для экранирования HTML-символов


def process_product(message, row):
    global selected_column

    if not selected_column:
        bot.send_message(message.chat.id, "Столбец для инвентаризации еще не выбран. Пожалуйста, начните сначала.")
        return

    try:
        product_name = sheet.cell(row, 1).value
        prev_column = (selected_column or 1) - 1
        prev_value = sheet.cell(row, prev_column).value if prev_column > 0 else "Нет данных"
        description = sheet.cell(row, 3).value or "Нет описания"

        # Экранируем HTML-символы перед отправкой
        product_name = html.escape(product_name)
        prev_value = html.escape(prev_value)
        description = html.escape(description)

        msg = (
            f"Строка: {row}\n"
            f"Наименование: {product_name}\n"
            f"Прошлая инвента: <b>{prev_value}</b>\n"
            f"Описание: {description}"
        )

        # Добавляем кнопку "Приостановить инвенту"
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        btn_stop = types.KeyboardButton("Приостановить инвенту")
        markup.add(btn_stop)

        bot.send_message(message.chat.id, msg, parse_mode='html', reply_markup=markup)
        bot.register_next_step_handler(message, handle_user_input, row, product_name)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при обработке продукта: {e}")


def start_editing(message):
    global selected_column

    check_and_set_date_silent()

    if not selected_column:
        bot.send_message(message.chat.id, "Ошибка: столбец для редактирования не найден. Начните сначала.")
        return

    try:
        last_row = len(sheet.col_values(1))
        all_values = sheet.batch_get([
            f"A4:A{last_row}",  # Названия продуктов
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])

        product_names = [item[0] for item in all_values[0]]
        current_values = [item[0] if item else "Не заполнено" for item in all_values[1]]

        # 📌 Оставляем только заполненные позиции
        filled_positions = [
            f"{i}. {name} - {value}"
            for i, (name, value) in enumerate(zip(product_names, current_values), start=4)
            if value != "Не заполнено"
        ]

        if not filled_positions:
            bot.send_message(message.chat.id, "Нет заполненных позиций для редактирования.")
            show_menu(message)
            return

        # 📌 Разбиваем список на группы по 20 элементов
        chunk_size = 20
        for i in range(0, len(filled_positions), chunk_size):
            bot.send_message(
                message.chat.id,
                "<b>Список позиций для редактирования:</b>\n" + "\n".join(filled_positions[i:i + chunk_size]),
                parse_mode='html'
            )

        # 📌 Добавляем кнопку "Назад"
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
        last_row = len(sheet.col_values(1))
        all_values = sheet.batch_get([
            f"A4:A{last_row}",  # Названия продуктов
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])

        product_names = [item[0].lower() for item in all_values[0]]
        current_values = [item[0] if item else "Не заполнено" for item in all_values[1]]

        user_input = message.text.strip().lower()

        # Если введён номер строки
        if user_input.isdigit():
            row_number = int(user_input)
            if 4 <= row_number <= last_row:
                process_edit_product(message, row_number)
                return

        # Если введено название позиции
        elif user_input in product_names:
            row_number = product_names.index(user_input) + 4
            process_edit_product(message, row_number)
            return

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
        product_name = sheet.cell(row, 1).value
        prev_column = (selected_column or 1) - 1
        prev_value = sheet.cell(row, prev_column).value if prev_column > 0 else "Нет данных"
        description = sheet.cell(row, 3).value or "Нет описания"
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

    # 📌 Обрабатываем новое значение отдельно, не вызывая handle_user_input()
    user_input = message.text.strip()

    try:
        sheet.update_cell(row, selected_column, user_input)
        bot.send_message(message.chat.id, f"Значение '{user_input}' успешно записано для {product_name}.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при записи данных: {e}")
        return

    # 📌 После редактирования не начинаем инвентаризацию, а сразу спрашиваем про продолжение
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
            reply_markup=types.ReplyKeyboardRemove()  # Убираем кнопки
        )
        bot.register_next_step_handler(message, process_edit_input)
    else:
        bot.send_message(
            message.chat.id,
            "Редактирование завершено. Возвращаемся в главное меню...",
            reply_markup=types.ReplyKeyboardRemove()  # Убираем кнопки
        )
        show_menu(message)


def handle_user_input(message, row, product_name):
    global selected_column

    if not selected_column:
        bot.send_message(message.chat.id, "Столбец для инвентаризации еще не выбран. Пожалуйста, начните сначала.")
        return

    user_input = message.text.strip().lower()

    if user_input == "приостановить инвенту":
        stop(message)  # Вызываем команду /stop
        return

    if user_input in ["много", "есть", "мало", "стоп"]:
        color = {"red": 0.95, "green": 0.80, "blue": 0.80} if user_input in ["крит", "мало", "стоп"] else \
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

        non_critical_value = extract_number(sheet.cell(row, 4).value)
        critical_value = extract_number(sheet.cell(row, 5).value)

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

    non_critical_items = []  # Не крит
    critical_items = []  # Крит
    stop_items = []  # Стоп

    try:
        today = datetime.now().strftime("%d.%m.%Y")  # Получаем текущую дату
        last_row = len(sheet.col_values(1))  # Определяем количество строк

        all_values = sheet.batch_get([
            f"A4:A{last_row}",  # Названия продуктов
            f"D4:D{last_row}",  # Не критические значения
            f"E4:E{last_row}",  # Критические значения
            f"{gspread.utils.rowcol_to_a1(4, selected_column)}:{gspread.utils.rowcol_to_a1(last_row, selected_column)}"
        ])

        product_names = [item[0] for item in all_values[0]]  # Названия
        non_critical_values = [extract_number(item[0]) if item else float('inf') for item in all_values[1]]  # Не крит
        critical_values = [extract_number(item[0]) if item else -1 for item in all_values[2]]  # Крит
        current_values = [item[0] if item else "" for item in all_values[3]]  # Текущие значения

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


# Добавляем команды для ручного управления скрытием/показом столбцов
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

    show_menu(message)  # Возвращаем пользователя в меню



def is_inventory_complete():
    """Проверяет, завершена ли инвентаризация."""
    product_names = sheet.col_values(1)[3:]  # Названия позиций
    last_row = len(product_names) + 3  # Определяем последнюю заполненную строку

    column_values = sheet.col_values(selected_column)[3:last_row]  # Значения инвентаризации

    for value in column_values:
        if not value or str(value).strip() == "":  # Добавляем проверку на None
            return False
    return True  # Если все заполнены


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

    product_names = sheet.col_values(1)[3:]  # Читаем названия позиций (столбец A, с 4-й строки)
    last_row = len(product_names) + 3

    all_values = sheet.batch_get([
        f"A4:A{last_row}",  # Названия продуктов
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


@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    global selected_column

    if message.text == "Инвента":
        check_and_set_date(message)

    elif message.text == "Редактировать":
        start_editing(message)

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
        bot.send_message(message.chat.id, "В каждом ПО, предназначенном для эксплуатации пользователями должна быть "
                                          "техническая поддержка, способная помочь в трудной ситуации. Так вот - "
                                          "здесь такого нет). По всем вопросам лучше лично обратиться к гениальному "
                                          "создателю этого бота.")

    elif message.text in ["Да", "Нет"]:
        if message.text == "Да":
            bot.send_message(
                message.chat.id,
                "Начинаем инвентаризацию!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            start_inventory(message)

        elif message.text == "Нет":
            bot.send_message(
                message.chat.id,
                "Редактирование отменено. Возвращаемся в главное меню...",
                reply_markup=types.ReplyKeyboardRemove()
            )
            show_menu(message)


if __name__ == "__main__":
    bot.polling(none_stop=True)