from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
import json
from config import admins


def get_keyboard(json_name):
    with open(json_name, encoding="utf-8") as json_file:
        keyboard_button = json.load(json_file)
    return keyboard_button


def get_admin_keyboard():
    return get_keyboard('storage_keyboard/admin_keyboard.json')


def get_user_keyboard():
    return get_keyboard('storage_keyboard/user_keyboard.json')


def menu_keyboard(user_id):
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(*[KeyboardButton(get_user_keyboard()[i]) for i in
                   ["start_marathon"]])
    if user_id in admins:
        keyboard.row(KeyboardButton(get_admin_keyboard()["admin_panel"]))
    return keyboard


def admin_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(*[KeyboardButton(get_admin_keyboard()[i]) for i in
                   ["mail_but", "statistics", "add_task", "change_tariff", "reset_marathon"]])
    keyboard.row(KeyboardButton(get_admin_keyboard()["user_panel"]))
    return keyboard


def mail_menu():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(*[KeyboardButton(get_admin_keyboard()[i]) for i in
                   ["textMail_but", "photoMail_but", "butMail_but", "preMail_but", "backMail_but", "startMail_but"]])
    return keyboard
