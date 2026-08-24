import re


PASSWORD_HINT = "Mật khẩu phải có ít nhất 6 ký tự, gồm chữ hoa, số và 1 ký tự đặc biệt."
_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{6,}$")


def validate_password(password: str) -> str | None:
    if not _PASSWORD_PATTERN.match(password):
        return PASSWORD_HINT
    return None
