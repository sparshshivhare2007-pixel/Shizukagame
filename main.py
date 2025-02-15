import os
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import UserNotParticipant
import random
import pymongo
from threading import Thread
from flask import Flask

# Bot details from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_HASH = "28e79037f0b334ef0503466c53f08af5"
API_ID = "29893020"

ADMIN_ID = int(os.getenv("ADMIN_ID", 6399386263))  # Admin ID for new user notifications

# Flask app for monitoring
flask_app = Flask(__name__)
start_time = time.time()

# MongoDB setup
mongo_client = pymongo.MongoClient(os.getenv("MONGO_URL", "Mango db url dalooo"))
db = mongo_client[os.getenv("MONGO_DB_NAME", "Champu")]
users_collection = db[os.getenv("MONGO_COLLECTION_NAME", "users")]
games_collection = db["games"]

# Pyrogram bot client
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Game data
player_data = {}

@flask_app.route('/')
def home():
    uptime_minutes = (time.time() - start_time) / 60
    user_count = users_collection.count_documents({})
    return f"Bot uptime: {uptime_minutes:.2f} minutes\nUnique users: {user_count}"

@app.on_message(filters.command("start"))
async def start_message(client, message):
    user_id = message.from_user.id
    user = message.from_user

    # Check if user is new
    if users_collection.count_documents({'user_id': user_id}) == 0:
        users_collection.insert_one({'user_id': user_id})
        await client.send_message(
            chat_id=ADMIN_ID,
            text=f"New User Alert:\n\nUser: {user.mention}\nUser ID: {user_id}\nTotal Users: {users_collection.count_documents({})}"
        )

    # Send welcome message with game options
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Battle Bet", callback_data="start_battle")],
        [InlineKeyboardButton("Rock Paper Scissors", callback_data="start_rps")],
        [InlineKeyboardButton("Trivia Quiz", callback_data="start_quiz")]
    ])
    await message.reply_text("Welcome to the Game Bot! Choose a game to play:", reply_markup=markup)

@app.on_callback_query(filters.regex("start_battle"))
async def start_battle(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    player_data[user_id] = {"health": 100, "attack": 10, "defense": 5}

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Attack", callback_data="battle_attack")],
        [InlineKeyboardButton("Defend", callback_data="battle_defend")],
        [InlineKeyboardButton("Flee", callback_data="battle_flee")]
    ])
    await callback_query.message.edit_text("You are in a battle! Choose your action:", reply_markup=markup)

@app.on_callback_query(filters.regex("battle_attack"))
async def battle_attack(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    enemy_attack = random.randint(5, 15)
    player_data[user_id]["health"] -= max(0, enemy_attack - player_data[user_id]["defense"])
    player_attack = player_data[user_id]["attack"]
    enemy_health = max(0, 100 - player_attack)

    if player_data[user_id]["health"] <= 0:
        await callback_query.message.edit_text("You have been defeated!")
        del player_data[user_id]
    elif enemy_health <= 0:
        await callback_query.message.edit_text("You have defeated the enemy!")
        del player_data[user_id]
    else:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Attack", callback_data="battle_attack")],
            [InlineKeyboardButton("Defend", callback_data="battle_defend")],
            [InlineKeyboardButton("Flee", callback_data="battle_flee")]
        ])
        await callback_query.message.edit_text(
            f"Your health: {player_data[user_id]['health']}\nEnemy health: {enemy_health}\nChoose your action:",
            reply_markup=markup
        )

@app.on_callback_query(filters.regex("battle_defend"))
async def battle_defend(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    player_data[user_id]["defense"] += 5
    await callback_query.message.edit_text("You defended! Your defense has increased.")

@app.on_callback_query(filters.regex("battle_flee"))
async def battle_flee(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    await callback_query.message.edit_text("You fled from the battle!")
    del player_data[user_id]

@app.on_callback_query(filters.regex("start_rps"))
async def start_rps(client, callback_query: CallbackQuery):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Rock", callback_data="rps_rock")],
        [InlineKeyboardButton("Paper", callback_data="rps_paper")],
        [InlineKeyboardButton("Scissors", callback_data="rps_scissors")]
    ])
    await callback_query.message.edit_text("Choose Rock, Paper, or Scissors:", reply_markup=markup)

@app.on_callback_query(filters.regex("rps_rock") | filters.regex("rps_paper") | filters.regex("rps_scissors"))
async def rps_choice(client, callback_query: CallbackQuery):
    user_choice = callback_query.data.split("_")[1]
    bot_choice = random.choice(["rock", "paper", "scissors"])
    result = ""

    if user_choice == bot_choice:
        result = "It's a tie!"
    elif (user_choice == "rock" and bot_choice == "scissors") or \
         (user_choice == "paper" and bot_choice == "rock") or \
         (user_choice == "scissors" and bot_choice == "paper"):
        result = "You win!"
    else:
        result = "You lose!"

    await callback_query.message.edit_text(f"You chose {user_choice}, I chose {bot_choice}. {result}")

@app.on_callback_query(filters.regex("start_quiz"))
async def start_quiz(client, callback_query: CallbackQuery):
    questions = [
        {"question": "What is the capital of France?", "answer": "Paris"},
        {"question": "What is 2 + 2?", "answer": "4"},
        {"question": "What is the largest planet?", "answer": "Jupiter"}
    ]
    question = random.choice(questions)
    await callback_query.message.edit_text(f"Quiz Time!\n\n{question['question']}")

@app.on_message(filters.command("quiz"))
async def quiz_answer(client, message):
    user_id = message.from_user.id
    if user_id in player_data and "quiz_question" in player_data[user_id]:
        if message.text.strip().lower() == player_data[user_id]["quiz_question"]["answer"].lower():
            await message.reply_text("Correct!")
        else:
            await message.reply_text("Incorrect!")
        del player_data[user_id]["quiz_question"]
    else:
        await message.reply_text("No active quiz question.")

if __name__ == "__main__":
    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080)).start()
    app.run()