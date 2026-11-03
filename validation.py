from datetime import date


def text(value, label, limit):
    value = str(value).strip()
    if not value or len(value) > limit:
        raise ValueError(f'{label}: требуется от 1 до {limit} символов.')
    return value


def integer(value, label, minimum=0):
    raw = str(value).strip()
    if not raw.isdecimal():
        raise ValueError(f'{label}: требуется целое число от {minimum}.')
    result = int(raw)
    if not minimum <= result <= 2147483647:
        raise ValueError(f'{label}: число вне допустимого диапазона.')
    return result


def iso_date(value):
    value = str(value).strip()
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ValueError('Дата должна иметь формат ГГГГ-ММ-ДД.') from None
    if result.isoformat() != value or result.year < 1000:
        raise ValueError('Дата должна иметь формат ГГГГ-ММ-ДД, год от 1000.')
    return value


def ensure_nonnegative(rows):
    balance = 0
    for row in rows:
        balance += row['quantity'] if row['kind'] == 'IN' else -row['quantity']
        if balance < 0:
            raise ValueError('Операция создаёт отрицательный остаток в истории товара.')
    return balance
