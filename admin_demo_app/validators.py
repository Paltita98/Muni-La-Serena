import re

from django.core.exceptions import ValidationError


def validate_chilean_rut(value):
    normalized = value.strip().replace('.', '').upper()
    match = re.fullmatch(r'(\d{7,8})-([\dK])', normalized)
    if not match:
        raise ValidationError('Ingresa un RUT válido con formato 19864005-0.')

    number, supplied_digit = match.groups()
    total = sum(
        int(digit) * ((index % 6) + 2)
        for index, digit in enumerate(reversed(number))
    )
    remainder = 11 - total % 11
    expected_digit = '0' if remainder == 11 else 'K' if remainder == 10 else str(remainder)
    if supplied_digit != expected_digit:
        raise ValidationError('El dígito verificador del RUT no es válido.')


class UppercasePasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError('La contraseña debe incluir al menos una mayúscula.')

    def get_help_text(self):
        return 'La contraseña debe incluir al menos una mayúscula.'


class SpecialCharacterPasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError('La contraseña debe incluir al menos un carácter especial.')

    def get_help_text(self):
        return 'La contraseña debe incluir al menos un carácter especial.'