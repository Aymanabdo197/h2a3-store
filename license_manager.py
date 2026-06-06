import os, json, time, hashlib, base64, secrets, platform, uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

LICENSE_FILE = os.path.join(os.path.expanduser('~'), '.hasnaa_license')
MASTER_SECRET = b'HASNAA_PRO_2024_SECURE_KEY'

def get_machine_id():
    raw = f"{platform.node()}-{uuid.getnode()}-{platform.machine()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def generate_trial_license():
    mid = get_machine_id()
    expiry = time.time() + (90 * 24 * 3600)
    payload = json.dumps({'mid': mid, 'exp': expiry, 'type': 'trial'})
    key = hashlib.sha256(MASTER_SECRET).digest()
    nonce = secrets.token_bytes(12)
    cipher = AESGCM(key)
    ct = cipher.encrypt(nonce, payload.encode(), b'')
    return base64.b64encode(nonce + ct).decode()

def verify_license():
    if not os.path.exists(LICENSE_FILE):
        lic = generate_trial_license()
        with open(LICENSE_FILE, 'w') as f:
            f.write(lic)
        os.chmod(LICENSE_FILE, 0o600)
        print("✅ تم تفعيل النسخة التجريبية (3 أشهر)")
        return True
    with open(LICENSE_FILE, 'r') as f:
        lic = f.read().strip()
    try:
        raw = base64.b64decode(lic)
        nonce, ct = raw[:12], raw[12:]
        key = hashlib.sha256(MASTER_SECRET).digest()
        cipher = AESGCM(key)
        plain = cipher.decrypt(nonce, ct, b'')
        data = json.loads(plain)
        if data.get('mid') != get_machine_id():
            print("❌ الترخيص غير صالح على هذا الجهاز")
            return False
        if time.time() > data['exp']:
            print("⏰ انتهت صلاحية الترخيص")
            print("💰 قم بالاشتراك بـ 5 دولار لكل 3 أشهر")
            return False
        remaining = int((data['exp'] - time.time()) / 86400)
        print(f"✅ الترخيص ساري – {remaining} يوم متبقي")
        return True
    except:
        print("❌ تلف ملف الترخيص – أعد التفعيل")
        os.remove(LICENSE_FILE)
        return False
