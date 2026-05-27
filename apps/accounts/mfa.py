import pyotp
import qrcode
import io
import base64

def generate_mfa_secret():
    return pyotp.random_base32()

def get_totp_uri(user, secret):
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name="Argus Service Desk"
    )

def generate_qr_code_base64(uri):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def verify_totp(secret, code):
    totp = pyotp.TOTP(secret)
    return totp.verify(code)
