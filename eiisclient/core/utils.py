import json


def to_json(data):
    """Форматирование данных в _read_json_file формат

    :param data: dict
    :return: json
    """
    return json.JSONEncoder(ensure_ascii=False, indent=4).encode(data)


def from_json(data):
    """Преобразование данных из json

    :param data: JSON-format
    :return:
    """
    return json.JSONDecoder().decode(data)
