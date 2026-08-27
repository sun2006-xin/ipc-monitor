from PyQt5.QtCore import QTranslator, QLocale
import os
from core.app_paths import R


class I18nManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.translator = QTranslator()
            cls._instance.current_lang = "zh"
        return cls._instance

    def load_language(self, lang_code, app):
        self.current_lang = lang_code
        app.removeTranslator(self.translator)
        qm_path = R(f"resources/i18n/{lang_code}.qm")
        if os.path.exists(qm_path):
            if self.translator.load(qm_path):
                app.installTranslator(self.translator)
                return True
        return False
