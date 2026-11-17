import os, json, base64, re
from urllib.request import Request,urlopen
from urllib.parse import urlsplit

def configured():
    return bool(os.getenv('RAZORPAY_KEY_ID') and os.getenv('RAZORPAY_KEY_SECRET'))
def call(path,data=None):
    if not configured():raise RuntimeError('Payment provider not configured')
    auth=base64.b64encode((os.environ['RAZORPAY_KEY_ID']+':'+os.environ['RAZORPAY_KEY_SECRET']).encode()).decode()
    req=Request('https://api.razorpay.com/v1/payment_links'+path,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Basic '+auth,'Content-Type':'application/json'})
    with urlopen(req,timeout=15) as r:return json.load(r)
def create(ref,amount,currency):
    j=call('',{'amount':amount,'currency':currency,'accept_partial':False,'reference_id':ref,'description':'Himachal Travel booking '+ref,'notify':{'sms':False,'email':False},'reminder_enable':False})
    if not re.fullmatch(r'plink_[A-Za-z0-9]+',j['id']) or urlsplit(j['short_url']).scheme!='https':raise RuntimeError('Unexpected provider response')
    return j
def fetch(pid):
    if not re.fullmatch(r'plink_[A-Za-z0-9]+',pid):raise ValueError('Invalid payment ID')
    return call('/'+pid)
