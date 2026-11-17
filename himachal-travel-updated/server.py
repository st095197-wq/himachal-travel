from notifications import notify
import payments, tempfile
from decimal import Decimal, InvalidOperation
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
    c.execute("CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, name TEXT NOT NULL, rating INTEGER NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL, status TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS booking_contacts (id TEXT PRIMARY KEY, phone TEXT, wa_opt_in INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS payments (id TEXT PRIMARY KEY, provider_id TEXT, url TEXT, amount INTEGER, currency TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS daily_views (day TEXT PRIMARY KEY, hits INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS trip_details (id TEXT PRIMARY KEY, details TEXT NOT NULL)")
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
        if p=='/robots.txt':self.out(200,b'User-agent: *\nDisallow: /admin\nDisallow: /api/\nSitemap: https://himachal-travel.onrender.com/sitemap.xml\n','text/plain');return
        if p=='/sitemap.xml':self.out(200,b'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://himachal-travel.onrender.com/</loc></url></urlset>','application/xml');return
        if p=='/api/admin/backup':
            if not self.auth():self.out(401,{'error':'Login required'});return
            with tempfile.TemporaryDirectory() as tmp:
                dest=Path(tmp)/'backup.sqlite3'
                with db() as c, sqlite3.connect(dest) as target:c.backup(target)
                self.out(200,dest.read_bytes(),'application/octet-stream');return
        if p=='/api/admin/metrics':
            if not self.auth():self.out(401,{'error':'Login required'});return
            with db() as c:self.out(200,{'views':[dict(r) for r in c.execute('SELECT * FROM daily_views ORDER BY day DESC LIMIT 30')],'payments':[dict(r) for r in c.execute('SELECT * FROM payments')],'payment_configured':payments.configured(),'test_mode':os.getenv('RAZORPAY_KEY_ID','').startswith('rzp_test_')});return
        if p=='/api/reviews':
            with db() as c:self.out(200,[dict(x) for x in c.execute("SELECT name,rating,body,created FROM reviews WHERE status='approved' ORDER BY created DESC")]);return
        if p=='/api/admin/reviews':
            if not self.auth():self.out(401,{'error':'Login required'});return
            with db() as c:self.out(200,[dict(x) for x in c.execute('SELECT * FROM reviews ORDER BY created DESC')]);return
        if p=='/api/tours':
            with db() as c:self.out(200,[dict(t,id=i) for i,t in enumerate(tours(c))]);return
        if p=='/api/admin':
            if not self.auth():self.out(401,{'error':'Login required'});return
            with db() as c:self.out(200,{'tours':tours(c),'bookings':[dict(x) for x in c.execute('SELECT b.*,q.name AS tour_name,q.price AS quoted_price, k.phone,k.wa_opt_in,td.details AS trip_details FROM bookings b LEFT JOIN booking_quotes q ON b.id=q.id LEFT JOIN booking_contacts k ON b.id=k.id LEFT JOIN trip_details td ON td.id=b.id ORDER BY created DESC')]});return
        if re.fullmatch(r'/photo/[a-f0-9]{32}',p):
            with db() as c:r=c.execute('SELECT mime,data FROM photos WHERE id=?',(p[7:],)).fetchone()
            if r:self.out(200,r['data'],r['mime']);return
        if p=='/admin':self.path='/admin.html';super().do_GET();return
        if p in ('/','/index.html'):
            with db() as c:c.execute('INSERT INTO daily_views VALUES (?,1) ON CONFLICT(day) DO UPDATE SET hits=hits+1',(datetime.date.today().isoformat(),))
        if p in ('/','/index.html','/style.css','/app.js','/extras.js','/mountains.svg','/admin.js','/admin.css'):super().do_GET();return
        self.send_error(404)
    def do_HEAD(self):
        if urlsplit(self.path).path in ('/','/index.html','/style.css','/app.js','/extras.js','/mountains.svg'):super().do_HEAD()
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
                if p in ('/api/admin/payment/create','/api/admin/payment/check','/api/admin/payment/cancel'):
                    ref=str(d['id'])
                    with db() as c:
                        c.execute('BEGIN IMMEDIATE')
                        b=c.execute('SELECT status FROM bookings WHERE id=?',(ref,)).fetchone()
                        r=c.execute('SELECT * FROM payments WHERE id=?',(ref,)).fetchone()
                        if not b:self.out(404,{'error':'Booking not found'});return
                        try:
                            if p.endswith('/create'):
                                if b['status']!='confirmed' or r:self.out(409,{'error':'Confirm availability first; only one payment link per booking'});return
                                currency=d['currency']; assert currency in ('INR','USD','EUR')
                                amount=Decimal(str(d['amount']))*100;assert amount.is_finite() and amount==amount.to_integral_value() and 100<=amount<=100000000
                                j=payments.create(ref,int(amount),currency)
                                c.execute('INSERT INTO payments VALUES (?,?,?,?,?,?)',(ref,j['id'],j['short_url'],int(amount),currency,'created'))
                            else:
                                if not r:self.out(404,{'error':'Payment link not found'});return
                                j=payments.fetch(r['provider_id'])
                                if j.get('reference_id')!=ref or j.get('currency')!=r['currency'] or j.get('amount')!=r['amount']:raise RuntimeError('Payment mismatch')
                                if p.endswith('/cancel') and j.get('status')=='created':j=payments.call('/'+r['provider_id']+'/cancel',{})
                                status=j.get('status','unknown')
                                if status=='paid' and j.get('amount_paid')!=r['amount']:raise RuntimeError('Payment amount mismatch')
                                c.execute('UPDATE payments SET status=? WHERE id=?',(status,ref))
                            c.commit();self.out(200,{'ok':True});return
                        except (ValueError,AssertionError,InvalidOperation):raise ValueError('Invalid amount')
                        except Exception:self.out(502,{'error':'Payment provider request failed. Check Razorpay dashboard before retrying.'});return
                if p=='/api/admin/review':
                    action=d['action']; assert action in ('approved','pending','delete')
                    with db() as c:
                        if action=='delete':c.execute('DELETE FROM reviews WHERE id=?',(d['id'],))
                        else:c.execute('UPDATE reviews SET status=? WHERE id=?',(action,d['id']))
                    self.out(200,{'ok':True});return
                if p=='/api/admin/trip-details':
                    ref=str(d['id']); details={k:str(d.get(k,'')).strip() for k in ('hotel','hotel_address','hotel_phone','pickup','pickup_time','driver','driver_phone','vehicle','instructions')}
                    assert all(len(v)<=500 for v in details.values())
                    for k in ('hotel_phone','driver_phone'): assert not details[k] or re.fullmatch(r'\+[1-9][0-9]{7,14}',details[k])
                    with db() as c:
                        if not c.execute('SELECT 1 FROM bookings WHERE id=?',(ref,)).fetchone():self.out(404,{'error':'Booking not found'});return
                        c.execute('INSERT OR REPLACE INTO trip_details VALUES (?,?)',(ref,json.dumps(details)))
                    self.out(200,{'ok':True});return
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
                        assert d['status'] in ('pending','confirmed','cancelled','completed')
                        c.execute('BEGIN IMMEDIATE')
                        row=c.execute('SELECT b.*,q.name AS tour_name,k.phone,k.wa_opt_in FROM bookings b LEFT JOIN booking_quotes q ON b.id=q.id LEFT JOIN booking_contacts k ON b.id=k.id WHERE b.id=?',(d['id'],)).fetchone()
                        if not row:self.out(404,{'error':'Booking not found'});return
                        payment=c.execute('SELECT status FROM payments WHERE id=?',(d['id'],)).fetchone()
                        if d['status']=='cancelled' and payment and payment['status'] not in ('cancelled','expired'):
                            self.out(409,{'error':'Cancel unpaid payment link first; paid bookings require manual refund and reconciliation.'});return
                        changed=row['status']!=d['status']; c.execute('UPDATE bookings SET status=? WHERE id=?',(d['status'],d['id']));c.commit()
                        result={}
                        if changed and d['status'] in ('confirmed','cancelled','completed'):result=notify(dict(row,status=d['status']))
                        self.out(200,{'ok':True,'notifications':result});return
                    else:self.send_error(404);return
                    c.execute("INSERT OR REPLACE INTO settings VALUES ('tours',?)",(json.dumps(ts),));c.commit()
                self.out(200,{'ok':True});return
            if p=='/api/reviews':
                assert n<=8000
                name=d['name'].strip();body=d['body'].strip();rating=d['rating']
                assert type(rating) is int and 1<=rating<=5 and 1<=len(name)<=80 and 10<=len(body)<=1500 and d.get('consent') is True and not d.get('website')
                now=datetime.datetime.now(datetime.timezone.utc)
                with db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    count=c.execute('SELECT COUNT(*) FROM reviews WHERE created>=?',((now-datetime.timedelta(hours=1)).isoformat(),)).fetchone()[0]
                    if count>=30:self.out(429,{'error':'Too many submissions. Try again later.'});return
                    c.execute('INSERT INTO reviews VALUES (?,?,?,?,?,?)',(uuid.uuid4().hex,name,rating,body,now.isoformat(),'pending'))
                self.out(201,{'ok':True});return
            if p in ('/api/track','/api/receipt'):
                ref=str(d.get('id','')).strip().upper();email=str(d.get('email','')).strip().lower()
                with db() as c:
                    b=c.execute('SELECT b.id,b.status,b.arrival,b.people,b.name,b.tour,q.name AS tour_name FROM bookings b LEFT JOIN booking_quotes q ON b.id=q.id WHERE b.id=? AND lower(b.email)=?',(ref,email)).fetchone()
                    if not b:self.out(404,{'error':'Booking not found'});return
                    r=c.execute('SELECT url,amount,currency,status FROM payments WHERE id=?',(ref,)).fetchone()
                    result=dict(b); result['tour_name']=result['tour_name'] or (tours(c)[b['tour']]['name'] if 0<=b['tour']<len(tours(c)) else 'Tour'); result.pop('tour',None)
                    td=c.execute('SELECT details FROM trip_details WHERE id=?',(ref,)).fetchone()
                    result['details']=json.loads(td[0]) if td and b['status'] in ('confirmed','completed') else {}
                    result['payment']=dict(r) if r and b['status'] in ('confirmed','completed') else None
                    if p=='/api/receipt':
                        if b['status'] not in ('confirmed','completed'):self.out(409,{'error':'Receipt available after confirmation'});return
                        from receipt import create_receipt
                        self.out(200,create_receipt(result),'application/pdf');return
                    self.out(200,result);return
            if p!='/api/bookings':self.send_error(404);return
            assert n<=16000
            tour=int(d['tour']);people=int(d['people']);date=datetime.date.fromisoformat(d['date']);name=d['name'].strip();email=d['email'].strip();country=d['country'].strip();notes=d.get('notes','')
            assert 1<=people<=20 and date>=datetime.date.today() and 0<len(name)<=100 and 0<len(country)<=100 and len(email)<=254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) and isinstance(notes,str) and len(notes)<=1000
            phone=str(d.get('phone','')).strip(); opt=d.get('wa_opt_in') is True
            assert re.fullmatch(r'\+[1-9][0-9]{7,14}',phone)
            ref='HT-'+uuid.uuid4().hex[:12].upper()
            with db() as c:
                ts=tours(c);assert 0<=tour<len(ts) and ts[tour].get('active',True)
                c.execute('INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?)',(ref,tour,date.isoformat(),people,name,email,country,notes,datetime.datetime.now(datetime.timezone.utc).isoformat(),'pending'));c.execute('INSERT INTO booking_quotes VALUES (?,?,?)',(ref,ts[tour]['name'],ts[tour]['price']));c.execute('INSERT INTO booking_contacts VALUES (?,?,?)',(ref,phone,int(opt)));c.commit()
            self.out(201,{'id':ref,'status':'pending'})
        except (ValueError,KeyError,TypeError,AttributeError,AssertionError,OverflowError):self.out(400,{'error':'Invalid details or file'})
        except sqlite3.Error:self.out(500,{'error':'Database unavailable'})
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
