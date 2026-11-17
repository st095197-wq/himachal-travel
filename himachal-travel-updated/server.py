from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, sqlite3, uuid, datetime, os, re
ROOT=Path(__file__).resolve().parent
DB=ROOT/'private_bookings.sqlite3'
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def do_GET(self):
        if self.path.split('?')[0] not in ('/','/index.html','/style.css','/app.js','/mountains.svg'):
            self.send_error(404);return
        super().do_GET()
    def do_HEAD(self):
        if self.path.split('?')[0] not in ('/','/index.html','/style.css','/app.js','/mountains.svg'):
            self.send_error(404);return
        super().do_HEAD()
    def reply(self,status,data):
        body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        if self.path!='/api/bookings': self.send_error(404);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16000: raise ValueError()
            d=json.loads(self.rfile.read(length));tour=int(d['tour']);people=int(d['people']);date=datetime.date.fromisoformat(d['date']);name=d['name'].strip();email=d['email'].strip();country=d['country'].strip();notes=d.get('notes','')
            if tour not in range(4) or not 1<=people<=20 or date<datetime.date.today() or not 0<len(name)<=100 or not 0<len(country)<=100 or len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not isinstance(notes,str) or len(notes)>1000:raise ValueError()
        except (ValueError,KeyError,TypeError,AttributeError):self.reply(400,{'error':'Invalid booking details'});return
        ref='HT-'+uuid.uuid4().hex[:12].upper()
        with sqlite3.connect(DB) as c:
            c.execute('CREATE TABLE IF NOT EXISTS bookings (id TEXT PRIMARY KEY, tour INTEGER, arrival TEXT, people INTEGER, name TEXT, email TEXT, country TEXT, notes TEXT, created TEXT, status TEXT)')
            c.execute('INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?)',(ref,tour,date.isoformat(),people,name,email,country,notes,datetime.datetime.now(datetime.timezone.utc).isoformat(),'pending'))
        self.reply(201,{'id':ref,'status':'pending'})
if __name__=='__main__':
    port=int(os.environ.get('PORT','8000')); print(f'Open http://localhost:{port}');ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
