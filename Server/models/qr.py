"""Pure QR encoding; no files, user names or remote URL fetching."""
import qrcode
from qrcode.exceptions import DataOverflowError


def encode(value):
    if not value.strip() or len(value.encode('utf-8')) > 1024:
        raise ValueError('Enter 1–1024 UTF-8 bytes')
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=4)
    qr.add_data(value.encode('utf-8'), optimize=0)
    try:
        qr.make(fit=True)
    except DataOverflowError:
        raise ValueError('QR capacity exceeded') from None
    return qr.get_matrix()
