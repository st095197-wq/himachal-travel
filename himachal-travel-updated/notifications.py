import os, json, re
from urllib.request import Request, urlopen

def post(url,headers,data):
    req=Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json',**headers},method='POST')
    with urlopen(req,timeout=12) as response:
        return 200<=response.status<300

def notify(b):
    results={}
    status=b['status']; ref=b['id']; tour=b.get('tour_name') or 'Himachal tour'
    text=f"Hello {b['name']},\nYour booking {ref} for {tour} is {status}.\nArrival: {b['arrival']} | Travellers: {b['people']}\nCheck your booking status and payment details at https://himachal-travel.onrender.com/#track.\nHimachal Travel with Gourav Shrama"
    key=os.getenv('BREVO_API_KEY'); sender=os.getenv('EMAIL_FROM')
    if key and sender:
        try:
            post('https://api.brevo.com/v3/smtp/email',{'api-key':key},{'sender':{'email':sender,'name':'Himachal Travel'},'to':[{'email':b['email']}],'subject':f'Booking {ref}: {status}','textContent':text});results['email']='accepted by provider'
        except Exception:results['email']='failed or unconfirmed'
    else:results['email']='not configured'
    if not b.get('wa_opt_in') or not b.get('phone'):
        results['whatsapp']='no consent or number';return results
    token=os.getenv('WA_ACCESS_TOKEN'); pid=os.getenv('WA_PHONE_NUMBER_ID',''); ver=os.getenv('WA_API_VERSION',''); template=os.getenv('WA_STATUS_TEMPLATE')
    if not(token and re.fullmatch(r'\d+',pid) and re.fullmatch(r'v\d+\.\d+',ver) and template):results['whatsapp']='not configured';return results
    try:
        post(f'https://graph.facebook.com/{ver}/{pid}/messages',{'Authorization':'Bearer '+token},{'messaging_product':'whatsapp','to':b['phone'].lstrip('+'),'type':'template','template':{'name':template,'language':{'code':os.getenv('WA_TEMPLATE_LANGUAGE','en_US')},'components':[{'type':'body','parameters':[{'type':'text','text':v} for v in (ref,status,tour)]}]}});results['whatsapp']='accepted by provider'
    except Exception:results['whatsapp']='failed or unconfirmed'
    return results
