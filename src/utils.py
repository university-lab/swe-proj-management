from PyQt5.QtGui import QFontDatabase
import qrc.resources
import hashlib


def add_font_resource(name):
    font_db = QFontDatabase()
    if font_db.addApplicationFont(name) == -1:
        print(f"failed to add font {name=}")
    else:
        print(f"successfully loaded font {name=}")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
