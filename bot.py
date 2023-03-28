import config
import messages

from datetime import datetime
import time

import telebot
from telebot import TeleBot, types, State

from pymongo import MongoClient
from bson.objectid import ObjectId  
############################################
####### для переназначения exception #######
import sys
import logging
import linecache
############################################

# Инициализируем телеграмм-бота
bot = telebot.TeleBot(config.TOKEN_BOT)

# Инициализируем клиент для работы с MongoDB
mongo_client = MongoClient(config.DB_URL)
db = mongo_client['everlastfandom']
users_collection = db["users"]
questionnaires_collection = db["questionnaires"]
fandoms_collection = db["fandoms"]
subscriptions_collection = db["subscriptions"]
achievements_collection = db["achievements"]


#Стартовая команда - /start, при ее нажатии бот проверяет есть ли запись о телеграмм пользователе в базе данных, если нет - то создает запись и выводить приветственное сообщение, с коротким описанием нашего проекта системы фандомов. Если запись о пользователе уже есть в БД, то выводится другое короткое приветственное сообщение.
@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        # Проверяем, есть ли запись о пользователе в базе данных
        user = users_collection.find_one({"telegram_id": message.chat.id})
        if user:
            # Если пользователь уже есть в БД, выводим короткое приветственное сообщение
            bot.send_message(message.chat.id, messages.ALREADY_REGISTERED_MESSAGE)
        else:
            # Если пользователь новый, создаем запись о нем в БД и выводим приветственное сообщение
            new_user = {
                "telegram_id": message.chat.id,
                "username": message.chat.username,
                "first_name": message.chat.first_name,
                "last_name": message.chat.last_name,
                "registration_date": datetime.now()
            }
            users_collection.insert_one(new_user)
            # Создаем инлайн-кнопку "Заполнить анкету"
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(text="➡️ Заполнить анкету", callback_data="fill_questionnaire")
            markup.add(button)
            bot.send_message(message.chat.id, messages.NEW_USER_MESSAGE, reply_markup=markup)
    except:
        PrintException()
        bot.send_message(m.chat.id, 'Какие-то неполадки. Попробуй еще раз.')

    
# Обработчик нажатия на кнопку "Заполнить анкету"
@bot.callback_query_handler(func=lambda call: call.data == "fill_questionnaire")
def fill_questionnaire_handler(call):
    # Записываем в БД айди пользователя и статус, что он заполняет анкету
    user_id = call.message.chat.id
    questionnaires_collection.insert_one({"user_id": user_id, "status": "in_progress"})
    # Отправляем первый вопрос
    bot.send_message(user_id, "Какой тип фандомов вам более всего нравится?", reply_markup=create_fandom_type_keyboard())


# Создание инлайн-клавиатуры для выбора типа фандома
def create_fandom_type_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    button_movies = types.InlineKeyboardButton(text="Фильмы", callback_data="movies")
    button_anime = types.InlineKeyboardButton(text="Аниме", callback_data="anime")
    button_games = types.InlineKeyboardButton(text="Игры", callback_data="games")
    keyboard.row(button_movies, button_anime, button_games)
    return keyboard


# Обработчик выбора типа фандома
@bot.callback_query_handler(func=lambda call: call.data in ["movies", "anime", "games"])
def fandom_type_handler(call):
    # Получаем пользователя из БД
    user = users_collection.find_one({"telegram_id": call.message.chat.id})
    # Обновляем статус анкеты в БД
    questionnaires_collection.update_one({"user_id": call.message.chat.id}, {"$set": {"fandom_type": call.data}})
    # Отправляем второй вопрос - выбор конкретного фандома
    bot.send_message(call.message.chat.id, "Выберите ваш любимый фандом:", reply_markup=create_fandoms_keyboard(call.data))


#Создание инлайн-клавиатуры для выбора конкретного фандома
def create_fandoms_keyboard(fandom_type):
    fandoms = fandoms_collection.find({"type": fandom_type})
    keyboard = types.InlineKeyboardMarkup()
    for fandom in fandoms:
        button = types.InlineKeyboardButton(text=fandom["fandom_name"], callback_data=f'questionnaire_choose_fandom_{fandom["_id"]}')
        keyboard.add(button)
    return keyboard


#Обработчик выбора конкретного фандома
@bot.callback_query_handler(func=lambda call: str(call.data).startswith('questionnaire_choose_fandom_'))
def fandom_handler(call):
    # Получаем пользователя из БД
    user = users_collection.find_one({"telegram_id": call.message.chat.id})
    # Получаем фандом из call.data
    fandom_id = ObjectId(str(call.data.replace('questionnaire_choose_fandom_', ''))
    fandom = fandoms_collection.find_one({"_id": fandom_id})
    # Обновляем запись в БД - конкретный фандом
    users_collection.update_one({"_id": ObjectId(user['_id'])}, {"$set": {"fandom": fandom['name']}})
    # Обновляем статус анкеты в БД
    questionnaires_collection.update_one({"user_id": call.message.chat.id}, {"$set": {"status": "completed"}})
    # Создаем инлайн-кнопку "Подписаться на новости фандома"
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(text="✉️ Подписаться на новости фандома", callback_data=f"subscribe_{fandom_id}")
    markup.add(button)
    # Отправляем сообщение с приветственным текстом и инлайн-кнопкой
    bot.send_message(call.message.chat.id, messages.QUESTIONNAIRE_COMPLETED_MESSAGE.format(fandom=fandom['fandom_name']), reply_markup=markup)


#Обработчик подписки на новости фандома
@bot.callback_query_handler(func=lambda call: call.data.startswith("subscribe_"))
def subscribe_handler(call):
    # Получаем пользователя из БД
    user = users_collection.find_one({"telegram_id": call.message.chat.id})
    # Получаем фандом
    fandom_id = call.data.replace('subscribe_', '')
    # Создаем запись о подписке в БД
    subscriptions_collection.insert_one({"user_id": user['telegram_id'], f"fandom_id_{fandom_id}": 'ok'})
    bot.send_message(call.message.chat.id, 'Вы успешно подписались на новости фандома!')
