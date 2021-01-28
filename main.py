import logging, time, threading, datetime

from config import token, admins, secret_key, shop_id
from mysql_dir.mysql_c import *
from storage_keyboard.keyboard_markup import *
from state import *
from payment.payment import *
from yookassa import Configuration, Payment

from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.exceptions import ChatNotFound
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import asyncio
from concurrent.futures import ProcessPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('asyncio').setLevel(logging.ERROR)
Configuration.configure(shop_id, secret_key)
# Initialize bot and dispatcher
bot = Bot(token=token)
dp = Dispatcher(bot, storage=MemoryStorage())


async def task_menu(order, db, user_id, message_id=None):
    db.get_task()
    tasks = db.c.fetchall()
    if tasks:
        db.get_task_data_text(tasks[order][0])
        task_data_text = db.c.fetchone()[2]
    else:
        task_data_text = "Пусто"
    keyboard = InlineKeyboardMarkup()
    if tasks:
        if order != 0:
            keyboard.row(InlineKeyboardButton("⏪", callback_data=f"task_iter_{order - 1}"))
        if order != len(tasks) - 1:
            keyboard.row(InlineKeyboardButton("⏩", callback_data=f"task_iter_{order + 1}"))
        keyboard.row(InlineKeyboardButton("Вложенные файлы", callback_data=f"task_file_{tasks[order][0]}"),
                     InlineKeyboardButton("Добавить вложенные файлы", callback_data=f"task_addfile_{tasks[order][0]}"))
        keyboard.row(InlineKeyboardButton("Редактировать задание", callback_data=f"task_edit_{tasks[order][0]}"),
                     InlineKeyboardButton("Удалить задание", callback_data=f"task_remove_{tasks[order][0]}"))
    keyboard.row(InlineKeyboardButton("Добавить задание➕", callback_data=f"task_add_{order}"))
    if message_id:
        await bot.edit_message_text(task_data_text, user_id, message_id, reply_markup=keyboard)
    else:
        await bot.send_message(user_id, task_data_text, reply_markup=keyboard)


async def payment_update():
    print("update payment")
    db = MySql()

    async def delete_payment(user_id, message_id):
        db.delete_payment(user_id)
        try:
            print(datetime.datetime.now())
            await bot.delete_message(user_id, message_id)
        except:
            pass

    db.get_payments()
    payments = db.c.fetchall()
    for payment in payments:
        status_payment = payment_present(Payment, payment[1])
        if status_payment:
            if status_payment == "succeeded":
                await delete_payment(payment[2], payment[6])
                await launch_marathon_for_user(payment[4], payment[2], 0)
            elif status_payment == "canceled":
                await delete_payment(payment[2], payment[6])
        else:
            await delete_payment(payment[2], payment[6])

    db.close_and_commit()


async def marathon_update():
    print("update marathon")
    db = MySql()
    db.select_user_marathon_by_tariff(7, 0)
    zero_tariff = db.c.fetchall()
    print(zero_tariff)
    db.select_user_marathon_by_tariff(30, 1)
    first_tariff = db.c.fetchall()
    print(first_tariff)
    for record in zero_tariff + first_tariff:
        user_id = record[5]
        tariff = int(record[3])
        if tariff in [0, 1]:
            db.select_message_id_task(user_id)
            message_ids = db.c.fetchall()
            for message_id in message_ids:
                await bot.delete_message(user_id, message_id[0])
        db.delete_user_task(user_id)
        db.insert_marathon_user(tariff, user_id, 0)
        await bot.send_message(user_id, "Время выполнения марафона истекло ⏱")
    db.close_and_commit()


async def launch_marathon_for_user(tariff, user_id, rank):
    db = MySql()
    db.get_task()
    tasks = db.c.fetchall()
    if rank == 0:
        print("start")
        db.insert_marathon_user(tariff, user_id, 1)
    if tasks and rank <= tasks[-1][2]:
        db.get_task_data_text(tasks[rank][0])
        task_data_text = db.c.fetchone()[2]
        msg = await bot.send_message(user_id, task_data_text)
        db.insert_user_task(user_id, tasks[rank][1], tasks[rank][0], tariff, msg.message_id)
        db.get_task_data_file(tasks[rank][0])
        tasks_file = db.c.fetchall()
        for task_file in tasks_file:
            if task_file[3] == 'photo':
                msg = await bot.send_photo(user_id, task_file[2])
            elif task_file[3] == 'audio':
                msg = await bot.send_audio(user_id, task_file[2])
            elif task_file[3] == 'document':
                msg = await bot.send_document(user_id, task_file[2])
            db.insert_user_task(user_id, tasks[rank][1], tasks[rank][0], tariff, msg.message_id)
        keyboard = InlineKeyboardMarkup().row(
            InlineKeyboardButton("Готово", callback_data=f"confirm_task_{tariff}_{rank}"))
        msg = await bot.send_message(user_id, "После выполнения задания нажмите <i>Готово</i>", parse_mode="HTML",
                               reply_markup=keyboard)
        db.insert_user_task(user_id, tasks[rank][1], tasks[rank][0], tariff, msg.message_id)
    else:
        db.insert_marathon_user(tariff, user_id, 0)
        await bot.send_message(user_id, "Марафон пройден успешно 🏁")
        if tariff in [0, 1]:
            db.select_message_id_task(user_id)
            message_ids = db.c.fetchall()
            for message_id in message_ids:
                try:
                    await bot.delete_message(user_id, message_id[0])
                except:
                    pass

        db.delete_user_task(user_id)
    db.close_and_commit()


async def mailing(user_ids, lively, banned, deleted, chat_id, mail_text, mail_photo, mail_link, mail_link_text):
    db = MySql()
    users_block = []
    start_mail_time = time.time()
    db.count_user()
    allusers = int(db.c.fetchone()[0])
    for user_id in user_ids:
        try:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(text=mail_link_text, url=mail_link))
            if str(mail_photo) != '0':
                if str(mail_link_text) != '0':
                    await bot.send_photo(user_id, caption=mail_text, photo=mail_photo, parse_mode='HTML',
                                         reply_markup=keyboard)
                else:
                    await bot.send_photo(user_id, caption=mail_text, parse_mode='HTML', photo=mail_photo)
            else:
                if str(mail_link_text) not in '0':
                    await bot.send_message(user_id, text=mail_text, parse_mode='HTML',
                                           reply_markup=keyboard)
                else:
                    await bot.send_message(user_id, parse_mode='HTML', text=mail_text)
            lively += 1
        except Exception as e:
            if 'bot was blocked by the user' in str(e):
                users_block.append(user_id)
                banned += 1
                # database is locked
    for user_id in users_block:
        db.c.execute("UPDATE users SET lively = (%s) WHERE user_id = (%s)", ('block', user_id,))
    admin_text = '*Рассылка окончена! ✅\n\n' \
                 '🙂 Количество живых пользователей:* {0}\n' \
                 '*% от числа всех:* {1}%\n' \
                 '*💩 Количество заблокировавших:* {3}\n' \
                 '*🕓 Время рассылки:* {2}'.format(str(lively), str(round(lively / allusers * 100, 2)),
                                                   str(round(time.time() - start_mail_time, 2)) + ' сек', str(banned))
    await bot.send_message(chat_id, admin_text, parse_mode='Markdown', reply_markup=admin_keyboard())
    db.close_and_commit()


async def admin_mailing(message: types.Message, state: FSMContext = None):
    db = MySql()
    chat_id = message.chat.id
    msgtext = message.text
    db.c.execute("""select textMail,photoMail,butTextMail,butUrlMail from users where user_id = %s""" % chat_id)
    data = db.c.fetchone()
    textMailUser = str(data[0])
    photoMailUser = str(data[1])
    butTextMail = str(data[2])
    butUrlMail = str(data[3])
    admin_btn_keyboard = get_admin_keyboard()
    if msgtext == admin_btn_keyboard["mail_but"]:
        await bot.send_message(chat_id, '*Вы попали в меню рассылки *📢\n\n'
                                        'Для возврата нажмите *{0}*\n\n'
                                        'Для отмены какой-либо операции нажмите /start\n\n'
                                        'Используйте *{1}* для предварительного просмотра рассылки, а *{2}* для начала'
                                        ' рассылки\n\n'
                                        'Текст рассылки поддерживает разметку *HTML*, то есть:\n'
                                        '<b>*Жирный*</b>\n'
                                        '<i>_Курсив_</i>\n'
                                        '<pre>`Моноширный`</pre>\n'
                                        '<a href="ссылка-на-сайт">[Обернуть текст в ссылку](test.ru)</a>'.format(
            admin_btn_keyboard["backMail_but"], admin_btn_keyboard["preMail_but"],
            admin_btn_keyboard["startMail_but"]
        ),
                               parse_mode="markdown", reply_markup=mail_menu())
        await MailingStates.admin_mailing.set()

    elif msgtext == admin_btn_keyboard["backMail_but"]:
        if state:
            await state.finish()
        await bot.send_message(chat_id, admin_btn_keyboard["backMail_but"], reply_markup=admin_keyboard())
        # bot.clear_step_handler(message)

    elif msgtext == admin_btn_keyboard["preMail_but"]:
        try:
            if butTextMail == '0' and butUrlMail == '0':
                if photoMailUser == '0':
                    await bot.send_message(chat_id, textMailUser, parse_mode='html', reply_markup=mail_menu())
                else:
                    await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                         reply_markup=mail_menu())
            else:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(text=butTextMail, url=butUrlMail))
                if photoMailUser == '0':
                    await bot.send_message(chat_id, textMailUser, parse_mode='html',
                                           reply_markup=keyboard)
                else:
                    await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                         reply_markup=keyboard)
        except:
            await bot.send_message(chat_id, "Упс..проверьте правильность введения данных")
        await MailingStates.admin_mailing.set()

    elif msgtext == admin_btn_keyboard["startMail_but"]:
        db.c.execute(
            """update users set textMail = 0, photoMail = 0,butTextMail = 0,butUrlMail = 0  where user_id = %s""" % chat_id)

        user_ids = []
        db.c.execute("""select user_id from users""")
        user_id = db.c.fetchone()
        while user_id is not None:
            user_ids.append(user_id[0])
            user_id = db.c.fetchone()
        if state:
            await state.finish()
        try:
            await bot.send_message(chat_id, 'Рассылка началась!',
                                   reply_markup=admin_keyboard())
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                await mailing(user_ids, 0, 0, 0, chat_id, textMailUser, photoMailUser, butUrlMail, butTextMail))

        except:
            pass


    elif admin_btn_keyboard["textMail_but"] == msgtext:
        await bot.send_message(chat_id,
                               'Введите текст рассылки. Допускаются теги HTML. Для отмены ввода нажите /start',
                               reply_markup=mail_menu())
        await ProcessTextMailing.text.set()

    elif admin_btn_keyboard["photoMail_but"] == msgtext:
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton(text='Добавить фото 📝', callback_data='editPhotoMail'))
        keyboard.row(InlineKeyboardButton(text='Удалить фото ❌', callback_data='deletePhoto'))
        await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
        await MailingStates.admin_mailing.set()

    elif admin_btn_keyboard["butMail_but"] == msgtext:
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton(text='Изменить текст кнопки 📝', callback_data='editTextBut'))
        keyboard.row(InlineKeyboardButton(text='Изменить ссылку кнопки 🔗', callback_data='editUrlBut'))
        keyboard.row(InlineKeyboardButton(text='Убрать всё к чертям 🙅‍♂', callback_data='deleteBut'))
        await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
        await MailingStates.admin_mailing.set()

    elif msgtext == "/start":
        # bot.clear_step_handler(message)
        await start(message)
        if state:
            await state.finish()

    else:
        # bot.clear_step_handler(message)
        await MailingStates.admin_mailing.set()


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    db = MySql()
    user_id = message.from_user.id
    db.store_user(user_id)
    db.close_and_commit()
    await bot.send_message(user_id, "Текст", reply_markup=menu_keyboard(user_id))


@dp.message_handler(
    lambda m: m.text == get_admin_keyboard()["mail_but"] and m.chat.id in admins and m.from_user.id == m.chat.id)
async def cheker(message: types.Message):
    db = MySql()
    admin_btn_keyboard = get_admin_keyboard()
    user_id = message.chat.id
    db.c.execute("select * from users where user_id = %s" % user_id)
    point = db.c.fetchone()
    if point is None:
        db.c.execute("insert into users (user_id, state) values (%s, %s)",
                     (user_id, 0))
    db.close_and_commit()
    # bot.clear_step_handler(message)
    await admin_mailing(message)


@dp.message_handler(lambda message: message.text in list(
    get_admin_keyboard().values()) and message.from_user.id == message.chat.id and message.from_user.id in admins)
async def take_massage_admin(message: types.Message):
    db = MySql()
    user_id = message.from_user.id
    text = message.text
    admin_keyboard_button = get_admin_keyboard()
    if text == "/start":
        await start(message)
    elif text == admin_keyboard_button["admin_panel"]:
        await bot.send_message(user_id, admin_keyboard_button["admin_panel"],
                               reply_markup=admin_keyboard())
    elif text == admin_keyboard_button["user_panel"]:
        await bot.send_message(user_id, admin_keyboard_button["user_panel"],
                               reply_markup=menu_keyboard(user_id))
    elif text == admin_keyboard_button["add_task"]:
        await task_menu(0, db, user_id)
    elif text == admin_keyboard_button["statistics"]:
        db = MySql()
        db.count_user()
        allusers = int(db.c.fetchone()[0])
        db.count_banned_user()
        banned = int(db.c.fetchone()[0])
        lively = allusers - banned
        admin_text = '*🙂 Количество живых пользователей:* {0}\n' \
                     '*% от числа всех:* {1}%\n' \
                     '*💩 Количество заблокировавших:* {2}'.format(str(lively), str(round(lively / allusers * 100, 2)),
                                                                   str(banned))
        await bot.send_message(user_id, admin_text, parse_mode='Markdown', reply_markup=admin_keyboard())
    elif text == admin_keyboard_button["change_tariff"]:
        db.get_tariffs()
        tariffs = db.c.fetchall()
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("Изменить средний тариф", callback_data="edit_middle"))
        keyboard.row(InlineKeyboardButton("Изменить максимальный тариф", callback_data="edit_max"))
        await bot.send_message(user_id,
                               f"<b>Средний тариф:</b> {tariffs[0][1]} рублей\n<b>Максимальный тариф:</b> {tariffs[1][1]} рублей",
                               parse_mode="HTML", reply_markup=keyboard)
    elif text == admin_keyboard_button["reset_marathon"]:
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("✅Подтвердить", callback_data=f"confirm_resetmarathon"),
                     InlineKeyboardButton("❌Отменить", callback_data=f"unconfirm"))
        await bot.send_message(user_id, "Подтвердите сбрасывание марафона", reply_markup=keyboard)
    db.close_and_commit()


@dp.message_handler(
    lambda message: message.text in list(get_user_keyboard().values()) and message.from_user.id == message.chat.id)
async def take_massage(message: types.Message, state: FSMContext):
    keyboard_button = get_user_keyboard()
    user_id = message.from_user.id
    text = message.text
    db = MySql()
    if text == "/start":
        await state.finish()
        await start(message)
    elif text == keyboard_button["start_marathon"]:
        if user_id in db.select_users_payments():
            await bot.send_message(user_id,
                                   "У Вас есть активная заявка на оплату марафона, оплатите марафон или подождите, пока заявка будет не активна")
        elif user_id in db.select_users_task():
            await bot.send_message(user_id,
                                   "Вы уже участвуете в марафоне")
        else:
            db.get_tariffs()
            tariffs = db.c.fetchall()
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton("Пройти марафон за 7 дней бесплатно", callback_data="marathon_buy_zero"))
            keyboard.row(
                InlineKeyboardButton(f"Пройти марафон за 30 дней - {tariffs[0][1]} ₽",
                                     callback_data="marathon_buy_first"))
            keyboard.row(InlineKeyboardButton(f"Пройти марафон без срока - {tariffs[1][1]} ₽ (обратная связь)",
                                              callback_data="marathon_buy_second"))
            await bot.send_message(user_id, "Описание, что человек получит на марафоне", reply_markup=keyboard)


@dp.callback_query_handler(state="*")
async def process_callback_messages(callback_query: types.CallbackQuery, state: FSMContext):
    '''Обработка callback запросов'''
    db = MySql()
    user_id = callback_query.from_user.id
    query_id = callback_query.id
    # CONNECT TO DATABASE
    try:
        message_id = callback_query.message.message_id
    except:
        message_id = callback_query.inline_message_id
    query_data = callback_query.data
    print(f'CallbackQuery: {user_id} -> {query_data}')
    start_data = query_data.split('_')[0]
    try:
        one_param = query_data.split('_')[1]
    except:
        one_param = None
    try:
        two_param = query_data.split('_')[2]
    except:
        two_param = None
    try:
        three_param = query_data.split('_')[3]
    except:
        three_param = None
    try:
        four_param = query_data.split('_')[4]
    except:
        four_param = None
    await bot.answer_callback_query(query_id)
    if start_data == "task":
        if one_param == "add":
            await bot.send_message(user_id, "Введите текст для задания:")
            db.get_task()
            task = db.c.fetchall()
            await state.update_data(edit=False)
            if task:
                await state.update_data(order=int(two_param) + 1)
            else:
                await state.update_data(order=int(two_param))
            await TaskText.text.set()
        elif one_param == "iter":
            await task_menu(int(two_param), db, user_id, message_id)
        elif one_param == "remove":
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton("✅Подтвердить", callback_data=f"confirm_deletetask_{two_param}"),
                         InlineKeyboardButton("❌Отменить", callback_data=f"unconfirm"))
            await bot.send_message(user_id, "Подтвердите удаление задания", reply_markup=keyboard)
        elif one_param == "edit":
            await bot.send_message(user_id, "Введите текст для задания:")
            await state.update_data(edit=True)
            await state.update_data(task_id=int(two_param))
            await TaskText.text.set()
        elif one_param == "addfile":
            await state.update_data(task_id=int(two_param))
            await bot.send_message(user_id, "Прикрепите файл (фото, аудио):")
            await TaskFile.file.set()
        elif one_param == "file":
            db.get_task_data_file(int(two_param))
            tasks_file = db.c.fetchall()
            for task_file in tasks_file:
                if task_file[3] == 'photo':
                    await bot.send_photo(user_id, task_file[2])
                elif task_file[3] == 'audio':
                    await bot.send_audio(user_id, task_file[2])
                elif task_file[3] == 'document':
                    await bot.send_document(user_id, task_file[2])
    elif start_data == "confirm":
        if one_param == "deletetask":
            db.delete_task(int(two_param))
            await bot.edit_message_text("Задание удалено", user_id, message_id)
        elif one_param == "resetmarathon":
            try:
                await bot.delete_message(user_id, message_id)
            except:
                pass
            db.reset_marathon()
            await bot.send_message(user_id, "Марафон обновлен")
        elif one_param == "task":
            try:
                await bot.delete_message(user_id, message_id)
            except:
                pass
            if int(two_param) in [0, 1]:
                await launch_marathon_for_user(int(two_param), user_id, int(three_param) + 1)
            else:
                await state.update_data(rank=int(three_param))
                await bot.send_message(user_id, "Введите ответ к заданию:")
                await AnswerState.answer.set()
    elif start_data == "unconfirm":
        await bot.delete_message(user_id, message_id)
    elif 'editTextBut' == start_data:
        # bot.clear_step_handler(callback_query.message)
        await bot.send_message(user_id, "Введите текст для кнопки")
        # bot.register_next_step_handler(callback_query.message, process_editTextBut)
        await ProcessEditTextBut.text.set()

    elif 'editUrlBut' == start_data:
        # bot.clear_step_handler(callback_query.message)
        await bot.send_message(user_id, 'Введите ссылку 📝', reply_markup=mail_menu())
        await ProcessEditUrlBut.text.set()

    elif 'deleteBut' == start_data:
        db.c.execute("""update users set butUrlMail = 0, butTextMail = 0 where user_id = (%s)""", (user_id,))
        await bot.send_message(user_id, 'Удалено! 🗑', reply_markup=mail_menu())
        await cheker(callback_query.message)

    elif 'editPhotoMail' == start_data:
        # bot.clear_step_handler(callback_query.message)
        await bot.send_message(user_id, 'Отправьте фотографию', reply_markup=mail_menu())
        await WaitPhoto.text.set()

    elif 'deletePhoto' == start_data:
        db.c.execute("""update users set photoMail = 0 where user_id = (%s)""", (user_id,))
        await bot.send_message(user_id, 'Фото удалено! ✅', reply_markup=mail_menu())
        await cheker(callback_query.message)
    elif 'edit' == start_data:
        if 'middle' == one_param:
            await bot.send_message(user_id, "Введите цену для среднего тарифного плана")
            await state.update_data(plan=1)
            await TariffNumber.number.set()
        elif 'max' == one_param:
            await bot.send_message(user_id, "Введите цену для максимального тарифного плана")
            await state.update_data(plan=2)
            await TariffNumber.number.set()
    elif start_data == 'marathon':
        if one_param == 'buy':
            if two_param == 'zero':
                if user_id in db.select_users_task():
                    await bot.send_message(user_id,
                                           "Вы уже участвуете в марафоне")
                    db.delete_payment(user_id)
                elif user_id in db.select_users_payments():
                    await bot.send_message(user_id,
                                           "У Вас есть активная заявка на оплату марафона, оплатите марафон или подождите, пока заявка будет не активна")
                else:
                    await launch_marathon_for_user(0, user_id, 0)
            elif two_param in ['first', 'second']:
                if user_id in db.select_users_task():
                    await bot.send_message(user_id,
                                           "Вы уже участвуете в марафоне")
                    db.delete_payment(user_id)
                elif user_id in db.select_users_payments():
                    await bot.send_message(user_id,
                                           "У Вас есть активная заявка на оплату марафона, оплатите марафон или подождите, пока заявка будет не активна")
                else:
                    db.get_tariffs()
                    tariffs = db.c.fetchall()
                    db.get_marathon()
                    curr_marathon = db.c.fetchone()[0]
                    payment = create_payment(Payment, tariffs[0][1] if two_param == 'first' else tariffs[1][1],
                                             user_id)
                    if payment:

                        keyboard = InlineKeyboardMarkup().row(InlineKeyboardButton(text="Оплатить",
                                                                                   url=payment._PaymentResponse__confirmation._ConfirmationRedirect__confirmation_url))
                        text = f"Cумма к оплате: {tariffs[0][1] if two_param == 'first' else tariffs[1][1]} ₽\n" \
                               f"Нажмите <b>Оплатить</b>, чтобы оплатить доступ к марафону\n" \
                               f"<i>Проверка платежа выполняется автоматически</i>"
                        msg = await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=keyboard)
                        db.insert_payment(payment._PaymentResponse__id, user_id, curr_marathon,
                                          1 if two_param == 'first' else 2, msg.message_id)
                    else:
                        await bot.send_message(user_id, "Ошибка❗️")

    db.close_and_commit()


@dp.message_handler(state=TaskText.text)
async def get_task_text(message: types.Message, state: FSMContext):
    db = MySql()
    text = message.text.strip()
    user_id = message.from_user.id
    if text == '/start':
        await state.finish()
        await start(message)
    elif text in list(get_admin_keyboard().values()):
        await state.finish()
        await take_massage_admin(message)
    else:
        data = await state.get_data()
        edit = data.get("edit")
        if edit:
            task_id = data.get("task_id")
            db.update_task_text(text, task_id)
            await bot.send_message(user_id, "Текст изменен")
        else:
            order = data.get("order")
            db.insert_task_text(order, text, 'text')
            await bot.send_message(user_id, "Текст добавлен")
        db.close_and_commit()
        await state.finish()


@dp.message_handler(state=TaskFile.file, content_types=['photo', 'audio', 'document', 'text'])
async def get_coin_name(message: types.Message, state: FSMContext):
    db = MySql()
    user_id = message.from_user.id
    if message.document:
        type_msg = "document"
        file_id = message.document.file_id
    elif message.photo:
        type_msg = "photo"
        file_id = message.photo[0].file_id
    elif message.audio:
        type_msg = "audio"
        file_id = message.audio.file_id
    elif message.text:
        text = message.text
        type_msg = "text"
    if type_msg in ["document", "photo", "audio"]:
        data = await state.get_data()
        task_id = data.get("task_id")
        db.insert_task(task_id, file_id, type_msg)
        db.close_and_commit()
        await bot.send_message(user_id, "Успешно добавлено✅")
        await state.finish()
    else:
        if text == '/start':
            await state.finish()
            await start(message)
        elif text in list(get_admin_keyboard().values()):
            await state.finish()
            await take_massage_admin(message)


@dp.message_handler(state=AnswerState.answer)
async def get_answer(message: types.Message, state: FSMContext):
    db = MySql()
    text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    rank = data.get("rank")
    if text == '/start':
        await state.finish()
        await start(message)
    elif text in list(get_user_keyboard().values()):
        await state.finish()
        await take_massage(message)
    else:
        username = f"{'@' + message.from_user.username if message.from_user.username else message.from_user.first_name + ' ' + message.from_user.last_name if message.from_user.last_name else message.from_user.first_name}"
        for admin in admins:
            await bot.send_message(admin,
                                   f"Ответ на вопрос № {rank + 1} от участника {username} (id: {user_id})\n" + text)
        await bot.send_message(user_id, "Ответ прийнят✅")
        await state.finish()
        await launch_marathon_for_user(2, user_id, rank + 1)


@dp.message_handler(state=TariffNumber.number)
async def get_tariff_number(message: types.Message, state: FSMContext):
    db = MySql()
    text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    plan = data.get("plan")
    if text == '/start':
        await state.finish()
        await start(message)
    elif text in list(get_admin_keyboard().values()):
        await state.finish()
        await take_massage_admin(message)
    elif text.isdigit():
        if int(text) > 0:
            db.update_tariff(plan, text)
            await bot.send_message(user_id, "Изменено")
            await state.finish()
        else:
            if plan == 1:
                await bot.send_message(user_id, "Введите цену для среднего тарифного плана")
                await state.update_data(plan=1)
                await TariffNumber.number.set()
            elif plan == 2:
                await bot.send_message(user_id, "Введите цену для максимального тарифного плана")
                await state.update_data(plan=2)
                await TariffNumber.number.set()
    else:
        if plan == 1:
            await bot.send_message(user_id, "Введите цену для среднего тарифного плана")
            await state.update_data(plan=1)
            await TariffNumber.number.set()
        elif plan == 2:
            await bot.send_message(user_id, "Введите цену для максимального тарифного плана")
            await state.update_data(plan=2)
            await TariffNumber.number.set()
    db.close_and_commit()


@dp.message_handler(state=MailingStates.admin_mailing)
async def get_telegram_id(message: types.Message, state: FSMContext):
    await admin_mailing(message, state)


@dp.message_handler(state=ProcessTextMailing.text)
async def get_telegram_id(message: types.Message, state: FSMContext):
    db = MySql()
    chat_id = message.from_user.id
    if message.text:
        if message.text == "/start":
            await bot.send_message(chat_id, "Действие отменено")
        else:
            db.c.execute("update users set textMail = (%s) where user_id = (%s)", (message.text,
                                                                                   chat_id))
            db.close_and_commit()
            await bot.send_message(chat_id, "Текст успешно установлен")
            await state.finish()
        await MailingStates.admin_mailing.set()


@dp.message_handler(state=ProcessEditTextBut.text)
async def get_telegram_id(message: types.Message, state: FSMContext):
    chat_id = message.from_user.id
    db = MySql()
    # c.execute("""update users set state = 0 where user_id = %s""" % (chat_id))
    db.c.execute("update users set butTextMail = (%s) where user_id = (%s)", (message.text,
                                                                              chat_id))
    db.close_and_commit()
    await bot.send_message(chat_id, 'Текст кнопки обновлен! ✅', reply_markup=mail_menu())
    await state.finish()


@dp.message_handler(state=ProcessEditUrlBut.text)
async def get_telegram_id(message: types.Message, state: FSMContext):
    if message.text:
        chat_id = message.from_user.id
        db = MySql()
        db.c.execute("update users set butUrlMail = (%s) where user_id = (%s)", (message.text,
                                                                                 chat_id))
        db.close_and_commit()
        await bot.send_message(chat_id, 'Ссылка кнопки обновлена! ✅', reply_markup=mail_menu())
        await state.finish()
        await cheker(message)


@dp.message_handler(state=CheckerState.check)
async def get_telegram_id(message: types.Message, state: FSMContext):
    user_id = message.chat.id
    db = MySql()
    db.c.execute("select * from users where user_id = %s" % user_id)
    point = db.c.fetchone()
    if point is None:
        db.c.execute("insert into users (user_id, state) values (%s, %s)",
                     (user_id, 0))
    db.close_and_commit()
    # bot.clear_step_handler(message)
    await state.finish()
    await admin_mailing(message)


@dp.message_handler(state=WaitPhoto.text, content_types=['photo'])
async def get_telegram_id(message: types.Message, state: FSMContext):
    print("photo")
    chat_id = message.from_user.id
    if message.content_type == 'photo':
        db = MySql()
        # msgphoto = message.json['photo'][0]['file_id']
        msgphoto = message.photo[0].file_id
        db.c.execute("""update users set photoMail = (%s) where user_id = (%s)""", (msgphoto, chat_id,))
        await bot.send_message(chat_id, 'Фото прикреплено! ✅', reply_markup=mail_menu())
        db.close_and_commit()
        # bot.register_next_step_handler(message, cheker)
        await state.finish()
        await CheckerState.check.set()
    else:
        await bot.send_message(chat_id, "Упс...", reply_markup=mail_menu())
        await CheckerState.check.set()
        # bot.register_next_step_handler(message, cheker)


def repeat(coro, loop):
    asyncio.ensure_future(coro(), loop=loop)
    loop.call_later(30, repeat, coro, loop)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.call_later(30, repeat, payment_update, loop)
    loop.call_later(30, repeat, marathon_update, loop)
    executor.start_polling(dp)
