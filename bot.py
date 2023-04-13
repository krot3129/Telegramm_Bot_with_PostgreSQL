import csv
import os
import psycopg2
from aiogram.types import ContentType
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.utils import executor
from logger import logger

load_dotenv()



# Connect to the database
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)

# Create a cursor object to execute SQL statements
cur = conn.cursor()

# Create a table
cur.execute('CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(50), balance INTEGER, admin BOOLEAN DEFAULT FALSE, is_blocked BOOLEAN DEFAULT FALSE)')

# Commit the changes
conn.commit()

bot_token = os.getenv("BOT_TOKEN")
bot = Bot(token=bot_token)
dp = Dispatcher(bot, storage=MemoryStorage())


async def add_to_database(username: str, balance: int):
    logger.debug('Добавление пользователя в БД')
    cur.execute("INSERT INTO users (username, balance) VALUES (%s, %s)", (username, balance))
    conn.commit()

def is_blocked(username: str) -> bool:
    logger.debug('Проверка пользователя на флаг блокировки')
    cur.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT FALSE")
    cur.execute("SELECT is_blocked FROM users WHERE username = %s", (username,))
    result = cur.fetchone()
    return result and result[0]

@dp.message_handler(Command('help'))
async def cmd_help(message: types.Message):
    commands = [
        '/start - start the bot',
        '/topup - top up the balance',
        '/admin - login to the admin panel',
        '/unload - unload users and their balance',
        '/add_balance - add balance to a user account',
        '/block - block a user',
        '/unblock - unblock a user',
        '/buy - buy a product',
    ]
    await message.answer('\n'.join(commands))


@dp.message_handler(Command('start'))
async def cmd_start(message: types.Message):
    logger.info('запуск команды старт')
    username = message.from_user.username

    # Add the user to the database
    await add_to_database(username, 0)

    await message.reply(f"Hi @{message.from_user.username}\n\n"
                        "User message:\n"
                        "I am a balance replenishment bot.\n"
                        "Click on the button to top up your balance",
                        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                            [types.InlineKeyboardButton(text="Top up balance", callback_data="topup")]
                        ]))


@dp.callback_query_handler(lambda c: c.data == 'topup')
async def process_callback_topup(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Enter the amount you want to top up the balance")


# Admin panel
# Command to login to the admin panel
@dp.message_handler(Command('admin'))
async def cmd_admin_login(message: types.Message, username=cur):
    username = message.from_user.username

    # Update the 'admin' column for the user in the database
    cur.execute("UPDATE users SET admin = TRUE WHERE username = %s", (username,))
    conn.commit()
    await message.reply('You are now logged in as admin')

async def update_balance(username: str, balance: int):
    cur.execute("UPDATE users SET balance = %s WHERE username = %s", (balance, username))
    conn.commit()

# Command to unload users and their balance


@dp.message_handler(Command('unload'))
async def cmd_unload_users(message: types.Message):
    # Check if the user has admin privileges
    conn = psycopg2.connect(
        host=os.getenv("HOST"),
        database=os.getenv("DATABASE"),
        user=os.getenv("USER"),
        password=os.getenv("PASSWORD")
    )
    cur = conn.cursor()
    username = message.from_user.username
    cur.execute("SELECT admin FROM users WHERE username = %s", (username,))
    is_admin = cur.fetchone()[0]
    if not is_admin:
        await message.reply("You don't have permission to use this command.")
        return

    # Retrieve the list of users and their balance from the database
    cur.execute("SELECT username, balance FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    with open('users.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['username', 'balance'])
        for row in rows:
            writer.writerow(row)

    # Send the CSV file as a response
    with open('users.csv', 'rb') as f:
        await bot.send_document(message.chat.id, document=f, caption='List of users and their balances')

@dp.message_handler(Command('add_balance'))
async def cmd_add_balance(message: types.Message):
    # Check if the user has admin privileges
    username = message.from_user.username
    cur.execute("SELECT admin FROM users WHERE username = %s", (username,))
    is_admin = cur.fetchone()[0]
    if not is_admin:
        await message.reply("You don't have permission to use this command.")
        return

    # Parse the username and balance from the message text
    try:
        _, username, balance_str = message.text.split()
        balance = int(balance_str)
    except ValueError:
        await message.reply("Invalid command syntax. Use /add_balance <username> <balance>")
        return

    # Update the user's balance in the database
    await update_balance(username, balance)

    # Send a confirmation message
    await message.reply(f"Balance updated: {username} now has {balance} in their account.")



PRICE = types.LabeledPrice(label="Подписка на 1 месяц", amount=500 * 100)  # в копейках (руб)


# buy
@dp.message_handler(commands=['buy'])
async def buy(message: types.Message):
    if os.getenv('PAYMENT_TOKEN'):
        await bot.send_message(message.chat.id, "Тестовый платеж!!!")

    await bot.send_invoice(message.chat.id,
                           title="Подписка на бота",
                           description="Активация подписки на бота на 1 месяц",
                           provider_token=os.getenv('PAYMENT_TOKEN'),
                           currency="rub",
                           photo_url="https://www.aroged.com/wp-content/uploads/2022/06/Telegram-has-a-premium-subscription.jpg",
                           photo_width=416,
                           photo_height=234,
                           photo_size=416,
                           is_flexible=False,
                           prices=[PRICE],
                           start_parameter="one-month-subscription",
                           payload="test-invoice-payload")


# pre checkout  (must be answered in 10 seconds)
@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


# successful payment
@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    print("SUCCESSFUL PAYMENT:")
    payment_info = message.successful_payment.to_python()
    for k, v in payment_info.items():
        print(f"{k} = {v}")

    await bot.send_message(message.chat.id,
                           f"Платёж на сумму {message.successful_payment.total_amount // 100} {message.successful_payment.currency} прошел успешно!!!")

@dp.message_handler(lambda message: is_blocked(message.from_user.username))
async def blocked_user_handler(message: types.Message):
    # Do not process messages from blocked users
    pass

@dp.message_handler(Command('block'))
async def cmd_block_user(message: types.Message):
    # Check if the user has admin privileges
    username = message.from_user.username
    cur.execute("SELECT admin FROM users WHERE username = %s", (username,))
    is_admin = cur.fetchone()[0]
    if not is_admin:
        await message.reply("You don't have permission to use this command.")
        return

    # Parse the username from the message text
    try:
        _, username_to_block = message.text.split()
    except ValueError:
        await message.reply("Invalid command syntax. Use /block <username>")
        return

    # Block the user in the database
    cur.execute("UPDATE users SET is_blocked = TRUE WHERE username = %s", (username_to_block,))
    conn.commit()

    # Send a confirmation message
    await message.reply(f"{username_to_block} has been blocked.")

@dp.message_handler(Command('unblock'))
async def cmd_unblock_user(message: types.Message):
    # Check if the user has admin privileges
    username = message.from_user.username
    cur.execute("SELECT admin FROM users WHERE username = %s", (username,))
    is_admin = cur.fetchone()[0]
    if not is_admin:
        await message.reply("You don't have permission to use this command.")
        return

    # Parse the username from the message text
    try:
        _, username_to_unblock = message.text.split()
    except ValueError:
        await message.reply("Invalid command syntax. Use /unblock <username>")
        return

    # Unblock the user in the database
    cur.execute("UPDATE users SET is_blocked = FALSE WHERE username = %s", (username_to_unblock,))
    conn.commit()

    # Send a confirmation message
    await message.reply(f"{username_to_unblock} has been unblocked.")


if __name__ == '__main__':
    logger.info('Бот запущен')
    executor.start_polling(dp, skip_updates=False)
