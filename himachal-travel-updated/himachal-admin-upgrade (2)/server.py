from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, sqlite3, uuid, datetime, os, re, hmac, secrets, time, base64, hashlib, threading
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('DATA_DIR',str(ROOT))); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'private_bookings.sqlite3'
PASSWORD=os.environ.get('ADMIN_PASSWORD',''); KEY=secrets.token_bytes(32)
LOGIN_LOCK=threading.Lock(); LOGIN_ATTEMPTS=[]

def db():
    c=sqlite3.connect(DB,timeout=10); c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS bookings (id TEXT PRIMARY KEY, tour INTEGER, arrival TEXT, people INTEGER, name TEXT, email TEXT, country TEXT, notes TEXT, created TEXT, status TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS photos (id TEXT PRIMARY KEY, mime TEXT, data BLOB)')
    c.execute('CREATE TABLE IF NOT EXISTS booking_quotes (id TEXT PRIMARY KEY, name TEXT, price REAL)')
    return c

def tours(c):
    r=c.execute("SELECT value FROM settings WHERE key='tours'").fetchone()
    return json.loads(r[0]) if r else json.loads((ROOT/'tours.json').read_text())

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','same-origin'); self.send_header('X-Frame-Options','DENY'); super().end_headers()
    def out(self,status,data,mime='application/json',cookie=None):
        body=json.dumps(data).encode() if mime=='application/json' else data
        self.send_response(status); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store')
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(body)
    def auth(self):
        m=re.search(r'(?:^|;\s*)htadmin=([\w.-]+)',self.headers.get('Cookie',''))
        if not PASSWORD or not m:return False
        try:
            stamp,nonce,sig=m[1].split('.'); return int(stamp)>time.time() and hmac.compare_digest(sig,hmac.new(KEY,f'{stamp}.{nonce}'.encode(),hashlib.sha256).hexdigest())
        except ValueError:return False
    def cookie(self,value,age):
        secure='; Secure' if os.environ.get('RENDER') or os.environ.get('COOKIE_SECURE')=='1' else ''
        return f'htadmin={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}'+secure
    def do_GET(self):
        p=urlsplit(self.path).path
        if p=='/api/tours':
            with db() as c:self.out(200,[dict(t,id=i) for i,t in enumerate(tours(c))]);return
        if p=='/api/admin':
            if not self.auth():self.out(401,{'error':'Login required'});return
            with db() as c:self.out(200,{'tours':tours(c),'bookings':[dict(x) for x in c.execute('SELECT b.*,q.name AS tour_name,q.price AS quoted_price FROM bookings b LEFT JOIN booking_quotes q ON b.id=q.id ORDER BY created DESC')]});return
        if re.fullmatch(r'/photo/[a-f0-9]{32}',p):
            with db() as c:r=c.execute('SELECT mime,data FROM photos WHERE id=?',(p[7:],)).fetchone()
            if r:self.out(200,r['data'],r['mime']);return
        if p=='/admin':self.path='/admin.html';super().do_GET();return
        if p in ('/','/index.html','/style.css','/app.js','/mountains.svg','/admin.js','/admin.css'):super().do_GET();return
        self.send_error(404)
    def do_HEAD(self):
        if urlsplit(self.path).path in ('/','/index.html','/style.css','/app.js','/mountains.svg'):super().do_HEAD()
        else:self.send_error(404)
    def do_POST(self):
        p=urlsplit(self.path).path
        try:
            n=int(self.headers.get('Content-Length','0')); assert 0<n<=8_000_000
            if self.headers.get_content_type()!='application/json':raise ValueError()
            d=json.loads(self.rfile.read(n)); assert isinstance(d,dict)
            if p.startswith('/api/admin/'):
                if self.headers.get('X-Admin-Request')!='1':self.out(403,{'error':'Forbidden'});return
                if p=='/api/admin/login':
                    if not PASSWORD:self.out(503,{'error':'Set ADMIN_PASSWORD on Render first'});return
                    with LOGIN_LOCK:
                        now=time.monotonic(); LOGIN_ATTEMPTS[:]=[x for x in LOGIN_ATTEMPTS if now-x<60]
                        if len(LOGIN_ATTEMPTS)>=10:self.out(429,{'error':'Too many attempts. Try again in a minute.'});return
                        LOGIN_ATTEMPTS.append(now)
                    time.sleep(.4)
                    if not hmac.compare_digest(str(d.get('password','')).encode(),PASSWORD.encode()):self.out(401,{'error':'Incorrect password'});return
                    value=f'{int(time.time()+28800)}.{secrets.token_hex(16)}'; value+='.'+hmac.new(KEY,value.encode(),hashlib.sha256).hexdigest();self.out(200,{'ok':True},cookie=self.cookie(value,28800));return
                if not self.auth():self.out(401,{'error':'Login required'});return
                if p=='/api/admin/logout':self.out(200,{'ok':True},cookie=self.cookie('',0));return
                with db() as c:
                    ts=tours(c)
                    if p=='/api/admin/tour':
                        i=int(d['id']); assert -1<=i<len(ts)
                        t={k:str(d[k]).strip() for k in ('name','days','place','desc')}; assert all(0<len(v)<=2000 for v in t.values())
                        price=float(d['price']); assert 0<price<=1000000
                        t.update(price=price,plan=[str(x)[:500] for x in d['plan'] if str(x).strip()][:60],active=bool(d['active']),photo=ts[i].get('photo','') if i>=0 else '')
                        if i<0:ts.append(t)
                        else:ts[i]=t
                    elif p=='/api/admin/photo':
                        i=int(d['id']);assert 0<=i<len(ts); raw=base64.b64decode(d['data'],validate=True);assert 0<len(raw)<=5_000_000
                        mime='image/jpeg' if raw.startswith(b'\xff\xd8\xff') else 'image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/webp' if raw[:4]==b'RIFF' and raw[8:12]==b'WEBP' else '';assert mime
                        pid=uuid.uuid4().hex;c.execute('INSERT INTO photos VALUES (?,?,?)',(pid,mime,raw));ts[i]['photo']=pid
                    elif p=='/api/admin/booking':
                        assert d['status'] in ('pending','confirmed','cancelled','completed');c.execute('UPDATE bookings SET status=? WHERE id=?',(d['status'],d['id']))
                    else:self.send_error(404);return
                    c.execute("INSERT OR REPLACE INTO settings VALUES ('tours',?)",(json.dumps(ts),));c.commit()
                self.out(200,{'ok':True});return
            if p!='/api/bookings':self.send_error(404);return
            assert n<=16000
            tour=int(d['tour']);people=int(d['people']);date=datetime.date.fromisoformat(d['date']);name=d['name'].strip();email=d['email'].strip();country=d['country'].strip();notes=d.get('notes','')
            assert 1<=people<=20 and date>=datetime.date.today() and 0<len(name)<=100 and 0<len(country)<=100 and len(email)<=254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) and isinstance(notes,str) and len(notes)<=1000
            ref='HT-'+uuid.uuid4().hex[:12].upper()
            with db() as c:
                ts=tours(c);assert 0<=tour<len(ts) and ts[tour].get('active',True)
                c.execute('INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?)',(ref,tour,date.isoformat(),people,name,email,country,notes,datetime.datetime.now(datetime.timezone.utc).isoformat(),'pending'));c.execute('INSERT INTO booking_quotes VALUES (?,?,?)',(ref,ts[tour]['name'],ts[tour]['price']));c.commit()
            self.out(201,{'id':ref,'status':'pending'})
        except (ValueError,KeyError,TypeError,AttributeError,AssertionError,OverflowError):self.out(400,{'error':'Invalid details or file'})
        except sqlite3.Error:self.out(500,{'error':'Database unavailable'})
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
