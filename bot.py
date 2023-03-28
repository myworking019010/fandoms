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


# клавиатура choose_mode
markup_start = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=False)
markup_start.row('👤 Профиль')
markup_start.row('🔮 Список наших фандомов')


#Стартовая команда - /start, при ее нажатии бот проверяет есть ли запись о телеграмм пользователе в базе данных, если нет - то создает запись и выводить приветственное сообщение, с коротким описанием нашего проекта системы фандомов. Если запись о пользователе уже есть в БД, то выводится другое короткое приветственное сообщение.
@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        # Проверяем, есть ли запись о пользователе в базе данных
        user = users_collection.find_one({"telegram_id": message.chat.id})
        bot.send_message(message.chat.id, 'Добро пожаловать! *картинка*', reply_markup = markup_start)
        if user:
            # Если пользователь уже есть в БД, выводим короткое приветственное сообщение
            bot.send_message(message.chat.id, messages.ALREADY_REGISTERED_MESSAGE, reply_markup = markup_start)
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






# Обработчик для вывода сообщения с информацией о cписке типов фандомов
@bot.message_handler(regexp='🔮 Список наших фандомов')
def show_our_fandoms_type_list(message):
    user = users_collection.find_one({"telegram_id": message.from_user.id})
    if not user:
        bot.send_message(message.chat.id, "К сожалению, я не нашел ваш профиль.")
        return
    
    reply_markup = types.InlineKeyboardMarkup()
    callback_button_1 = types.InlineKeyboardButton(text="Фильмы", callback_data="sofl_movies")
    callback_button_2 = types.InlineKeyboardButton(text="Аниме", callback_data="sofl_anime")
    callback_button_3 = types.InlineKeyboardButton(text="Игры", callback_data="sofl_games")
    reply_markup.add(callback_button_1)
    reply_markup.add(callback_button_2)
    reply_markup.add(callback_button_3)
    
    
    bot.send_message(message.chat.id, f'❕ Выберите тип фандомов из списка:', reply_markup = reply_markup)


# обработчик для кнопки sofl_
@bot.callback_query_handler(func=lambda call: call.data.startswith('sofl_'))
def show_our_fandoms_list_callback(call):
    fandom_type = call.data.replace('sofl_', '')
    
    fandoms = fandoms_collection.find({"fandom_type": fandom_type})
    
    reply_markup = types.InlineKeyboardMarkup()
    for fandom in fandoms:
        button = types.InlineKeyboardButton(text=fandom["fandom_name"], callback_data=f'current_sofl_{fandom["_id"]}')
        reply_markup.add(button)
    button = types.InlineKeyboardButton(text=f'↩️ Вернуться в главное меню', callback_data=f'back_to_menu')
    reply_markup.add(button)
    
    bot.send_message(call.message.chat.id, f'Текущий список фандомов в этом разделе:', reply_markup = reply_markup)



# обработчик для кнопки current_sofl_
@bot.callback_query_handler(func=lambda call: call.data.startswith('current_sofl_'))
def show_our_current_fandoms_callback(call):
    fandom_id = call.data.replace('current_sofl_', '')
    
    fandom = fandoms_collection.find_one({"_id": ObjectId(fandom_id)})
    
    reply_markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(text=f'Вступить в фандом!', callback_data=f'choose_current_sofl_{fandom_id}')
    reply_markup.add(button)
        
    bot.send_message(call.message.chat.id, f'Название фандома: {fandom["fandom_name"]}\nОписание фандома: {fandom["fandom_description"]}', reply_markup = reply_markup)


# обработчик для кнопки choose_current_sofl_
@bot.callback_query_handler(func=lambda call: call.data.startswith('choose_current_sofl_'))
def show_our_current_fandoms_callback(call):
    fandom_id = call.data.replace('choose_current_sofl_', '')
    
    fandom = fandoms_collection.find_one({"_id": ObjectId(fandom_id)})
    
    # здесь бот будет проверять подписку на основной канал проекта и основной канал выбранного фандома
    
    check_subscriptions = subscriptions_collection.find_one({'user_id': call.message.chat.id})
    if check_subscriptions:
        subscriptions_collection.update_one({'user_id': call.message.chat.id}, {"$set": {"active_fandoms_id": {fandom_id: 'active'}}})
    else: 
        subscriptions_collection.insert_one({"user_id": call.message.chat.id, f"active_fandoms_id": {fandom_id: fandom_id}})
    
    bot.send_message(call.message.chat.id, f'Отлично, проверил твои подписки, ты принят в фандом! Вот ознакомительные ссылки: *бла-бла-бла*')





# Обработчик для вывода сообщения с информацией о профиле
@bot.message_handler(regexp='👤 Профиль')
def show_profile(message):
    user = users_collection.find_one({"telegram_id": message.from_user.id})
    if not user:
        bot.send_message(message.chat.id, "К сожалению, я не нашел ваш профиль.")
        return
    registration_date = user['registration_date'].strftime('%d.%m.%Y')

    first_fandom = user['first_fandom']
    first_name = user['first_name']
    profile_text = f"👤 {first_name}\n🆔 {message.from_user.id}\n\n📅 Дата регистрации: {registration_date}\n1️⃣ Первый выбранный фандом: {first_fandom}"
    
    keyboard = types.InlineKeyboardMarkup()
    callback_button_1 = types.InlineKeyboardButton(text="Посмотреть анкету", callback_data="show_questionnaire")
    callback_button_2 = types.InlineKeyboardButton(text="Мои фандомы", callback_data="show_my_fandoms")
    keyboard.add(callback_button_1)
    keyboard.add(callback_button_2)
    
    bot.send_message(message.chat.id, profile_text, reply_markup=keyboard)


# обработчик для кнопки показать анкету
@bot.callback_query_handler(func=lambda call: call.data == 'show_questionnaire')
def show_questionnaire_callback(call):
    user_id = call.from_user.id
    questionnaire = questionnaires_collection.find_one({"user_id": user_id})
    if not questionnaire:
        bot.send_message(call.message.chat.id, "Вы еще не заполнили анкету.")
        return
    
    age = questionnaire['age']
    gender = questionnaire['gender']
    fandom_type = questionnaire['fandom_type']
    status = questionnaire['status']
    fandom_names = ', '.join(questionnaire.get('fandom_names', []))
    
    questionnaire_text = f"👶 Возраст: {age}\n🚹 Пол: {gender}\n🎭 Тип фандома: {fandom_type}\n📝 Статус анкеты: {status}"
    if fandom_names:
        questionnaire_text += f"\nЛюбимые фандомы: {fandom_names}"
    
    bot.send_message(call.message.chat.id, questionnaire_text)



# обработчик для кнопки Мои фандомы
@bot.callback_query_handler(func=lambda call: call.data == 'show_my_fandoms')
def show_my_fandoms_callback(call):
    current_user_subscriptions = subscriptions_collection.find_one({'user_id': call.message.chat.id})
    
    message_to_send = 'Сейчас ты состоишь в следующих фандомах:\n'
    number = 1
    for fandom in current_user_subscriptions["active_fandoms_id"]:
        #print(fandom)
        current_fandom = fandoms_collection.find_one({'_id': ObjectId(fandom)})
        message_to_send += f'#{number} - {current_fandom["fandom_name"]}\n'
    
    bot.send_message(call.message.chat.id, message_to_send)
    pass


    
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
    
    # Сохраняем статус анкеты в БД, чтобы потом вернуться к ней, если пользователь откажется от ответа
    questionnaires_collection.update_one({"user_id": call.message.chat.id, "status": "in_progress"}, {"$set": {"age": "None"}})
    # Добавляем кнопку "Пропустить вопрос"
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    skip_button = types.KeyboardButton(text="Пропустить вопрос")
    markup.add(skip_button)
    # Запрашиваем возраст пользователя
    message = bot.send_message(call.message.chat.id, "Укажите ваш возраст:", reply_markup = markup)
    bot.register_next_step_handler(message, age_received_handler)


# Обработчик ответа на вопрос о возрасте пользователя
def age_received_handler(message):
    try:
        user_id = message.chat.id
        if message.text.lower() == "пропустить вопрос":
            # Если пользователь пропускает вопрос, то сохраняем ответ в БД как None и переходим к следующему вопросу
            questionnaires_collection.update_one({"user_id": user_id, "status": "in_progress"}, {"$set": {"age": None}})
            next_question(user_id)
        else:
            # Если пользователь указал возраст, то сохраняем его в БД и переходим к следующему вопросу
            if message.text.isdecimal():
                if int(message.text) > 0:
                    age = int(message.text)
                    questionnaires_collection.update_one({"user_id": user_id, "status": "in_progress"}, {"$set": {"age": age}})
                    next_question_woman_or_man(user_id)
                else:
                    # Добавляем кнопку "Пропустить вопрос"
                    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
                    skip_button = types.KeyboardButton(text="Пропустить вопрос")
                    markup.add(skip_button)
                    msg = bot.send_message(user_id, "Некорректный ввод. Пожалуйста, укажите свой возраст цифрами.", reply_markup=markup)
                    bot.register_next_step_handler(message, age_received_handler)
            else:
                # Добавляем кнопку "Пропустить вопрос"
                markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
                skip_button = types.KeyboardButton(text="Пропустить вопрос")
                markup.add(skip_button)
                msg = bot.send_message(user_id, "Некорректный ввод. Пожалуйста, укажите свой возраст цифрами.", reply_markup=markup)
                bot.register_next_step_handler(message, age_received_handler)
    except Exception as e:
        print(e)
        bot.send_message(user_id, "Что-то пошло не так, попробуйте заново.")


def next_question_woman_or_man(user_id):
    question = "Какого вы пола?"
    
    markup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton(text="Мужской", callback_data="questionnaire_choose_gender_man")
    button2 = types.InlineKeyboardButton(text="Женский", callback_data="questionnaire_choose_gender_woman")
    button3 = types.InlineKeyboardButton(text="Не хочу отвечать", callback_data="questionnaire_choose_gender_no_answer")
    markup.add(button1)
    markup.add(button2)
    markup.add(button3)
    
    bot.send_message(chat_id=user_id, text=question, reply_markup = markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('questionnaire_choose_gender_'))
def choose_gender_callback(call):
    gender = None
    if call.data == "questionnaire_choose_gender_man":
        gender = "мужуской"
    elif call.data == "questionnaire_choose_gender_woman":
        gender = "женский"
    elif call.data == "questionnaire_choose_gender_no_answer":
        gender = "без ответа"

    if gender:
        # Записываем ответ пользователя в базу данных
        questionnaires_collection.update_one({"user_id": call.message.chat.id, "status": "in_progress"}, {"$set": {"gender": gender}})
        
        fandom_type = questionnaires_collection.find_one({"user_id": call.message.chat.id})
        # Отправляем следующий вопрос
        bot.send_message(call.message.chat.id, 'Выберите фандом, в который бы вступили первым:', reply_markup=create_fandoms_keyboard(fandom_type["fandom_type"]))
        bot.answer_callback_query(callback_query_id=call.id, text="Ответ записан")
    else:
        bot.answer_callback_query(callback_query_id=call.id, text="Выберите один из вариантов")



#Создание инлайн-клавиатуры для выбора конкретного фандома
def create_fandoms_keyboard(fandom_type):
    fandoms = fandoms_collection.find({"fandom_type": fandom_type})
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
    fandom_id = ObjectId(str(call.data.replace('questionnaire_choose_fandom_', '')))
    fandom = fandoms_collection.find_one({"_id": fandom_id})
    # Обновляем запись в БД - конкретный фандом
    users_collection.update_one({"_id": ObjectId(user['_id'])}, {"$set": {"first_fandom": fandom['fandom_name']}})
    # Обновляем статус анкеты в БД
    questionnaires_collection.update_one({"user_id": call.message.chat.id}, {"$set": {"first_fandom": fandom['fandom_name']}})
    questionnaires_collection.update_one({"user_id": call.message.chat.id}, {"$set": {"status": "completed"}})
    # Создаем инлайн-кнопку "Подписаться на новости фандома"
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(text="✉️ Подписаться на новости фандома", callback_data=f"subscribe_{fandom_id}")
    markup.add(button)
    # Отправляем сообщение с приветственным текстом и инлайн-кнопкой
    bot.send_message(call.message.chat.id, messages.QUESTIONNAIRE_COMPLETED_MESSAGE, reply_markup=markup)


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





















# settings 
@bot.message_handler(commands=['settings'])
def settings_handler(message):
    # Здесь можно определить, что делать при получении команды /settings
    pass
    
    
# help 
@bot.message_handler(commands=['help'])
def help_handler(message):
    bot.send_message(message.chat.id, messages.HELP_MESSAGE)
    pass



######################## переназначение Exception #############################
def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    bot.send_message(admin, 'LINE {} "{}")\n\nТип ошибки: {}\n\nОшибка: {}'.format(lineno, line.strip(), exc_type, exc_obj))


#запуск бота
bot.polling()
