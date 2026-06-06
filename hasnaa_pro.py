#!/usr/bin/env python3
"""
HASNAA PRO v10.0 – Production Stable Release
"""
import os, sys, time, re, json, logging, argparse, asyncio, base64, secrets
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode
import aiohttp
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HASNAA")

# إضافة المسار لاستيراد الوحدات
sys.path.insert(0, os.path.dirname(__file__))
from hasnaa.utils.license_manager import verify_license
from hasnaa.utils.proxy_manager import ProxyManager

class StableScanner:
    def __init__(self, url, concurrency=10, stealth=False, proxy=None):
        self.url = url
        self.concurrency = concurrency
        self.proxy = proxy
        self.findings = []
        self.sem = asyncio.Semaphore(concurrency)
        self.timeout = aiohttp.ClientTimeout(total=15)
        self.session = None

    async def _fetch(self, url):
        async with self.sem:
            try:
                async with self.session.get(url, timeout=self.timeout) as resp:
                    html = await resp.text()
                    return html, resp.status, resp.headers
            except Exception as e:
                logger.debug(f"Request failed: {e}")
                return None, None, None

    async def _test_payload(self, url, param, payload, check_func, vuln_type):
        test_url = url.replace('FUZZ', payload) if 'FUZZ' in url else url
        html, _, _ = await self._fetch(test_url)
        if html is None: return
        is_vuln, desc = check_func(html, payload, 0)
        if is_vuln:
            self.findings.append({
                'type': vuln_type, 'payload': payload, 'desc': desc,
                'url': test_url, 'param': param, 'time': datetime.now().strftime('%H:%M:%S')
            })
            logger.warning(f"[!] {vuln_type}: {payload[:50]} ({desc})")

    async def _scan_endpoint(self, url, param, check_func, vuln_type, payloads):
        tasks = [self._test_payload(url, param, p, check_func, vuln_type) for p in payloads]
        await asyncio.gather(*tasks)

    def run(self):
        async def main():
            conn = aiohttp.TCPConnector(limit=self.concurrency, force_close=True)
            self.session = aiohttp.ClientSession(connector=conn, headers={'User-Agent':'Mozilla/5.0'})
            if self.proxy:
                self.session.proxy = self.proxy
            parsed = urlparse(self.url)
            params = {}
            if parsed.query:
                params = {k: v[0] for k,v in parse_qs(parsed.query).items()}
            if not params:
                params['test'] = '1'
            for param, value in params.items():
                qs = parse_qs(parsed.query) if parsed.query else {}
                qs[param] = ['FUZZ']
                new_qs = urlencode(qs, doseq=True)
                test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_qs}"
                await self._scan_endpoint(test_url, param, self._check_sql, 'SQLi', SQL_PAYLOADS)
                await self._scan_endpoint(test_url, param, self._check_xss, 'XSS', XSS_PAYLOADS)
                await self._scan_endpoint(test_url, param, self._check_lfi, 'LFI', LFI_PAYLOADS)
                await self._scan_endpoint(test_url, param, self._check_cmdi, 'CMDi', CMDE_PAYLOADS)
            await self.session.close()
            return self.findings
        return asyncio.run(main())

    def _check_sql(self, html, payload, elapsed):
        errors = ['sql syntax', 'mysql_fetch', 'unclosed quotation', 'error in your sql']
        if any(e in html.lower() for e in errors): return True, 'Error-based SQLi'
        return False, ''
    def _check_xss(self, html, payload, elapsed):
        clean = payload.split('//')[0] if '//' in payload else payload
        return (clean and clean in html, 'Reflected XSS')
    def _check_lfi(self, html, payload, elapsed):
        return (any(k in html for k in ['root:x:0:0:', 'www-data:', '/bin/bash']), 'LFI')
    def _check_cmdi(self, html, payload, elapsed):
        return (any(k in html for k in ['uid=', 'gid=', 'groups=']), 'CMDi')

SQL_PAYLOADS = ["' OR 1=1--", "' UNION SELECT NULL--", "admin'--"]
XSS_PAYLOADS = ['<script>alert(1)</script>', '"><script>alert(1)</script>']
LFI_PAYLOADS = ['../../etc/passwd', '....//....//etc/passwd']
CMDE_PAYLOADS = [';whoami', '|id']

def generate_html_report(findings, target_url, scan_time):
    html = f"""<!DOCTYPE html><html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><title>تقرير HASNAA PRO</title>
<style>body{{font-family:'Segoe UI';padding:40px}}h1{{color:#10b981}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:8px}}th{{background:#10b981;color:#fff}}</style></head>
<body><h1>تقرير فحص الأمان – HASNAA PRO v10.0</h1>
<p>الهدف: {target_url} | التاريخ: {scan_time} | الثغرات: {len(findings)}</p>
<table><tr><th>#</th><th>النوع</th><th>الوصف</th><th>الحمولة</th></tr>
"""
    for i, f in enumerate(findings, 1):
        html += f"<tr><td>{i}</td><td>{f['type']}</td><td>{f['desc']}</td><td><code>{f['payload'][:60]}</code></td></tr>\n"
    html += "</table></body></html>"
    return html

def main():
    if not verify_license():
        sys.exit(1)
    parser = argparse.ArgumentParser(description="HASNAA PRO v10.0")
    parser.add_argument('--url', required=True)
    parser.add_argument('--concurrency', type=int, default=10)
    parser.add_argument('--proxy')
    parser.add_argument('--report', help='حفظ تقرير HTML')
    args = parser.parse_args()

    if not args.url.startswith('http'): args.url = 'http://' + args.url

    scanner = StableScanner(args.url, concurrency=args.concurrency, proxy=args.proxy)
    start_time = datetime.now()
    findings = scanner.run()
    scan_time = datetime.now() - start_time

    print(f"\n✅ اكتمل الفحص في {scan_time.total_seconds():.1f} ثانية. تم اكتشاف {len(findings)} ثغرة.")
    for f in findings:
        print(f"  - {f['type']}: {f['payload'][:50]} ({f['desc']})")

    report_file = args.report or f"report_{start_time.strftime('%Y%m%d_%H%M%S')}.html"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(generate_html_report(findings, args.url, start_time.strftime('%Y-%m-%d %H:%M:%S')))
    print(f"📄 التقرير: {report_file}")

if __name__ == '__main__':
    main()
