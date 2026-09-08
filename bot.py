import asyncio
import os
from collections import defaultdict
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env")


# ============================================================
# BOT
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# WEB SERVER
# ============================================================

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


# ============================================================
# DATA
# ============================================================

# Пока храним операции только в памяти.
# После перезапуска бота они исчезнут.
operations = []


CATEGORIES = [
    ("👕 Одежда", "clothes"),
    ("👟 Обувь", "shoes"),
    ("💄 Красота", "beauty"),
    ("🧹 Хозяйство", "household"),
    ("💻 Техника", "tech"),
    ("📱 Подписки", "subscriptions"),
    ("☕ Кафе", "cafe"),
    ("🛒 Продукты", "groceries"),
    ("🎁 Праздники", "holidays"),
    ("🍫 Перекусы", "snacks"),
    ("💊 Медицина", "medicine"),
    ("🍽 Посуда", "dishes"),
    ("🏠 Коммуналка", "utilities"),
    ("🏠 Аренда", "rent"),
    ("👨‍👩‍👧 Семья", "family"),
    ("💳 Долги", "debts"),
    ("🎨 Хобби", "hobby"),
    ("🎮 Развлечения", "entertainment"),
    ("🏦 Банк", "bank"),
    ("✈️ Путешествия", "travel"),
    ("🚗 Транспорт", "transport"),
    ("💰 Зарплата", "salary"),
]


# ============================================================
# FSM
# ============================================================

class CreateOperation(StatesGroup):
    type = State()
    currency = State()
    amount = State()
    category = State()
    description = State()
    confirmation = State()


# ============================================================
# HELPERS
# ============================================================

def currency_symbol(currency: str) -> str:
    if currency == "AMD":
        return "֏"

    return "₽"


def format_amount(amount: float) -> str:
    if amount.is_integer():
        return f"{int(amount):,}".replace(",", " ")

    return f"{amount:,.2f}".replace(",", " ")


def get_category_name(category_id: str) -> str:
    for name, value in CATEGORIES:
        if value == category_id:
            return name

    return category_id


def format_operation(operation: dict) -> str:
    if operation["type"] == "income":
        sign = "+"
    else:
        sign = "-"

    symbol = currency_symbol(operation["currency"])

    return (
        f"{sign}{format_amount(operation['amount'])} {symbol} "
        f"— {operation['category_name']}\n"
        f"   {operation['description']}"
    )


# ============================================================
# KEYBOARDS
# ============================================================

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Создать операцию",
                    callback_data="create_operation",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Посмотреть бюджет",
                    callback_data="view_budget",
                )
            ],
        ]
    )


def operation_type_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟢 Приход",
                    callback_data="type_income",
                ),
                InlineKeyboardButton(
                    text="🔴 Расход",
                    callback_data="type_expense",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel",
                )
            ],
        ]
    )


def currency_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇦🇲 Драмы",
                    callback_data="currency_AMD",
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Рубли",
                    callback_data="currency_RUB",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_to_type",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel",
                ),
            ],
        ]
    )


def categories_menu() -> InlineKeyboardMarkup:
    buttons = []

    for i in range(0, len(CATEGORIES), 2):
        row = []

        for name, value in CATEGORIES[i:i + 2]:
            row.append(
                InlineKeyboardButton(
                    text=name,
                    callback_data=f"category_{value}",
                )
            )

        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def confirmation_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Отправить",
                    callback_data="confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel",
                )
            ],
        ]
    )


def budget_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Баланс",
                    callback_data="balance",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Сегодня",
                    callback_data="today",
                ),
                InlineKeyboardButton(
                    text="📆 Месяц",
                    callback_data="month",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="statistics",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Главное меню",
                    callback_data="main_menu",
                )
            ],
        ]
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "💰 <b>Семейный бюджет</b>\n\n"
        "Что хотите сделать?",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


# ============================================================
# MAIN MENU
# ============================================================

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    await callback.message.edit_text(
        "💰 <b>Семейный бюджет</b>\n\n"
        "Что хотите сделать?",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# CREATE OPERATION
# ============================================================

@dp.callback_query(F.data == "create_operation")
async def create_operation(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    await state.set_state(CreateOperation.type)

    await callback.message.edit_text(
        "➕ <b>Создание операции</b>\n\n"
        "Выберите тип операции:",
        reply_markup=operation_type_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# TYPE
# ============================================================

@dp.callback_query(F.data.in_({
    "type_income",
    "type_expense",
}))
async def select_type(
    callback: CallbackQuery,
    state: FSMContext,
):
    operation_type = (
        "income"
        if callback.data == "type_income"
        else "expense"
    )

    await state.update_data(
        type=operation_type
    )

    await state.set_state(
        CreateOperation.currency
    )

    if operation_type == "income":
        text = (
            "🟢 <b>Приход</b>\n\n"
            "Выберите валюту:"
        )
    else:
        text = (
            "🔴 <b>Расход</b>\n\n"
            "Выберите валюту:"
        )

    await callback.message.edit_text(
        text,
        reply_markup=currency_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# CURRENCY
# ============================================================

@dp.callback_query(F.data.startswith("currency_"))
async def select_currency(
    callback: CallbackQuery,
    state: FSMContext,
):
    data = await state.get_data()

    if not data.get("type"):
        await callback.answer(
            "Сначала начните создание операции.",
            show_alert=True,
        )
        return

    currency = callback.data.removeprefix(
        "currency_"
    )

    await state.update_data(
        currency=currency
    )

    await state.set_state(
        CreateOperation.amount
    )

    symbol = currency_symbol(currency)

    await callback.message.edit_text(
        f"💱 Валюта: <b>{symbol}</b>\n\n"
        "💰 Введите сумму:",
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# BACK TO TYPE
# ============================================================

@dp.callback_query(F.data == "back_to_type")
async def back_to_type(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.set_state(
        CreateOperation.type
    )

    await callback.message.edit_text(
        "Выберите тип операции:",
        reply_markup=operation_type_menu(),
    )

    await callback.answer()


# ============================================================
# AMOUNT
# ============================================================

@dp.message(CreateOperation.amount)
async def enter_amount(
    message: Message,
    state: FSMContext,
):
    if not message.text:
        await message.answer(
            "❌ Введите сумму числом."
        )
        return

    text = (
        message.text
        .strip()
        .replace(" ", "")
        .replace(",", ".")
    )

    try:
        amount = float(text)

    except ValueError:
        await message.answer(
            "❌ Не удалось распознать сумму.\n\n"
            "Например:\n"
            "3500\n"
            "3500.50"
        )
        return

    if amount <= 0:
        await message.answer(
            "❌ Сумма должна быть больше нуля."
        )
        return

    await state.update_data(
        amount=amount
    )

    await state.set_state(
        CreateOperation.category
    )

    await message.answer(
        "📂 <b>Выберите категорию:</b>",
        reply_markup=categories_menu(),
        parse_mode="HTML",
    )


# ============================================================
# CATEGORY
# ============================================================

@dp.callback_query(F.data.startswith("category_"))
async def select_category(
    callback: CallbackQuery,
    state: FSMContext,
):
    data = await state.get_data()

    if not data.get("type"):
        await callback.answer(
            "Сначала начните создание операции.",
            show_alert=True,
        )
        return

    category_id = callback.data.removeprefix(
        "category_"
    )

    category_name = get_category_name(
        category_id
    )

    await state.update_data(
        category_id=category_id,
        category_name=category_name,
    )

    await state.set_state(
        CreateOperation.description
    )

    await callback.message.edit_text(
        f"📂 Категория: <b>{category_name}</b>\n\n"
        "📝 Напишите описание операции:",
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# DESCRIPTION
# ============================================================

@dp.message(CreateOperation.description)
async def enter_description(
    message: Message,
    state: FSMContext,
):
    if not message.text:
        await message.answer(
            "❌ Введите описание операции."
        )
        return

    description = message.text.strip()

    if not description:
        await message.answer(
            "❌ Описание не может быть пустым."
        )
        return

    await state.update_data(
        description=description
    )

    await state.set_state(
        CreateOperation.confirmation
    )

    data = await state.get_data()

    if data["type"] == "income":
        type_text = "🟢 Приход"
    else:
        type_text = "🔴 Расход"

    symbol = currency_symbol(
        data["currency"]
    )

    await message.answer(
        "🔎 <b>Проверьте операцию</b>\n\n"
        f"{type_text}\n"
        f"💰 Сумма: "
        f"<b>{format_amount(data['amount'])} {symbol}</b>\n"
        f"📂 Категория: "
        f"{data['category_name']}\n"
        f"📝 Описание: "
        f"{data['description']}\n\n"
        "Отправить операцию?",
        reply_markup=confirmation_menu(),
        parse_mode="HTML",
    )


# ============================================================
# CONFIRM
# ============================================================

@dp.callback_query(
    CreateOperation.confirmation,
    F.data == "confirm",
)
async def confirm_operation(
    callback: CallbackQuery,
    state: FSMContext,
):
    data = await state.get_data()

    operation = {
        "type": data["type"],
        "currency": data["currency"],
        "amount": data["amount"],
        "category_id": data["category_id"],
        "category_name": data["category_name"],
        "description": data["description"],
        "created_at": datetime.now(timezone.utc),
        "user_id": callback.from_user.id,
    }

    operations.append(operation)

    await state.clear()

    await callback.message.edit_text(
        "✅ <b>Операция сохранена!</b>\n\n"
        f"{format_operation(operation)}",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# VIEW BUDGET
# ============================================================

@dp.callback_query(F.data == "view_budget")
async def view_budget(
    callback: CallbackQuery,
):
    await callback.message.edit_text(
        "📊 <b>Бюджет</b>\n\n"
        "Выберите, что показать:",
        reply_markup=budget_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# BALANCE
# ============================================================

@dp.callback_query(F.data == "balance")
async def balance(
    callback: CallbackQuery,
):
    balances = defaultdict(float)

    for operation in operations:
        if operation["type"] == "income":
            balances[
                operation["currency"]
            ] += operation["amount"]

        else:
            balances[
                operation["currency"]
            ] -= operation["amount"]

    amd = balances["AMD"]
    rub = balances["RUB"]

    await callback.message.edit_text(
        "💰 <b>Текущий баланс</b>\n\n"
        f"🇦🇲 <b>Драмы:</b> "
        f"{format_amount(amd)} ֏\n\n"
        f"🇷🇺 <b>Рубли:</b> "
        f"{format_amount(rub)} ₽",
        reply_markup=budget_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# TODAY
# ============================================================

@dp.callback_query(F.data == "today")
async def today(
    callback: CallbackQuery,
):
    now = datetime.now(timezone.utc)

    start_of_day = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    today_operations = [
        operation
        for operation in operations
        if operation["created_at"] >= start_of_day
    ]

    if not today_operations:
        text = (
            "📅 <b>Сегодня</b>\n\n"
            "Операций сегодня нет."
        )

    else:
        income = defaultdict(float)
        expense = defaultdict(float)

        for operation in today_operations:
            if operation["type"] == "income":
                income[
                    operation["currency"]
                ] += operation["amount"]

            else:
                expense[
                    operation["currency"]
                ] += operation["amount"]

        text = "📅 <b>Сегодня</b>\n\n"

        for currency, symbol in [
            ("AMD", "֏"),
            ("RUB", "₽"),
        ]:
            if income[currency] or expense[currency]:
                text += (
                    f"<b>{symbol}</b>\n"
                    f"🟢 Приход: "
                    f"+{format_amount(income[currency])} "
                    f"{symbol}\n"
                    f"🔴 Расход: "
                    f"-{format_amount(expense[currency])} "
                    f"{symbol}\n\n"
                )

        text += "<b>Операции:</b>\n\n"

        for operation in reversed(
            today_operations
        ):
            text += (
                format_operation(operation)
                + "\n\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=budget_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# MONTH
# ============================================================

@dp.callback_query(F.data == "month")
async def month(
    callback: CallbackQuery,
):
    now = datetime.now(timezone.utc)

    start_of_month = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    month_operations = [
        operation
        for operation in operations
        if operation["created_at"] >= start_of_month
    ]

    if not month_operations:
        text = (
            "📆 <b>Текущий месяц</b>\n\n"
            "Операций за этот месяц нет."
        )

    else:
        income = defaultdict(float)
        expense = defaultdict(float)

        for operation in month_operations:
            if operation["type"] == "income":
                income[
                    operation["currency"]
                ] += operation["amount"]

            else:
                expense[
                    operation["currency"]
                ] += operation["amount"]

        text = "📆 <b>Текущий месяц</b>\n\n"

        for currency, symbol in [
            ("AMD", "֏"),
            ("RUB", "₽"),
        ]:
            if income[currency] or expense[currency]:
                current_balance = (
                    income[currency]
                    - expense[currency]
                )

                text += (
                    f"<b>{symbol}</b>\n"
                    f"🟢 Приход: "
                    f"+{format_amount(income[currency])} "
                    f"{symbol}\n"
                    f"🔴 Расход: "
                    f"-{format_amount(expense[currency])} "
                    f"{symbol}\n"
                    f"💰 Баланс: "
                    f"{format_amount(current_balance)} "
                    f"{symbol}\n\n"
                )

    await callback.message.edit_text(
        text,
        reply_markup=budget_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# STATISTICS
# ============================================================

@dp.callback_query(F.data == "statistics")
async def statistics(
    callback: CallbackQuery,
):
    now = datetime.now(timezone.utc)

    start_of_month = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    category_totals = {
        "AMD": defaultdict(float),
        "RUB": defaultdict(float),
    }

    for operation in operations:
        if (
            operation["type"] == "expense"
            and operation["created_at"]
            >= start_of_month
        ):
            category_totals[
                operation["currency"]
            ][
                operation["category_name"]
            ] += operation["amount"]

    text = "📊 <b>Расходы за месяц</b>\n"

    has_data = False

    for currency, symbol in [
        ("AMD", "֏"),
        ("RUB", "₽"),
    ]:
        categories = category_totals[currency]

        if not categories:
            continue

        has_data = True

        text += f"\n<b>{symbol}</b>\n"

        sorted_categories = sorted(
            categories.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        for category, amount in sorted_categories:
            text += (
                f"{category}: "
                f"{format_amount(amount)} "
                f"{symbol}\n"
            )

    if not has_data:
        text += (
            "\nРасходов за этот месяц пока нет."
        )

    await callback.message.edit_text(
        text,
        reply_markup=budget_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# CANCEL
# ============================================================

@dp.callback_query(F.data == "cancel")
async def cancel(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Операция отменена.</b>\n\n"
        "Что хотите сделать?",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# RUN TELEGRAM BOT
# ============================================================

async def start_bot():
    print("🤖 Telegram бот запущен")

    await dp.start_polling(bot)


# ============================================================
# RUN WEB SERVER
# ============================================================

async def start_web():
    port = int(
        os.getenv("PORT", "10000")
    )

    print(
        f"🌐 HTTP сервер запускается "
        f"на порту {port}"
    )

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )

    server = uvicorn.Server(config)

    await server.serve()


# ============================================================
# MAIN
# ============================================================

async def main():
    await asyncio.gather(
        start_bot(),
        start_web(),
    )


if __name__ == "__main__":
    asyncio.run(main())