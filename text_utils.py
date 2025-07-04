

class TextUtils:
    @staticmethod
    def is_empty(s):
        return s is None or (isinstance(s, str) and not s.strip())