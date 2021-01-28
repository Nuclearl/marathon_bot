import uuid


def create_payment(payment, amount, user_id):
    try:
        payment = payment.create({
            "amount": {
                "value": f"{amount}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://yookassa.ru/"
            },
            "capture": True,
            "description": f"{user_id}",
        }, uuid.uuid4())
        return payment
    except:
        return False


def payment_present(payment, payment_id):
    try:
        payment = payment.find_one(payment_id)
        return payment._PaymentResponse__status
    except:
        return False
