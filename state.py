from aiogram.dispatcher.filters.state import State, StatesGroup


class TaskText(StatesGroup):
    text = State()


class TariffNumber(StatesGroup):
    number = State()


class TaskFile(StatesGroup):
    file = State()


class MailingStates(StatesGroup):
    admin_mailing = State()


class ProcessTextMailing(StatesGroup):
    text = State()


class ProcessEditTextBut(StatesGroup):
    text = State()


class ProcessEditUrlBut(StatesGroup):
    text = State()


class WaitPhoto(StatesGroup):
    text = State()


class CheckerState(StatesGroup):
    check = State()


class AnswerState(StatesGroup):
    answer = State()
