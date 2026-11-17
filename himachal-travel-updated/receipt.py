from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

def create_receipt(b):
    buf=BytesIO(); styles=getSampleStyleSheet(); styles['Title'].textColor=colors.HexColor('#153b60'); story=[Paragraph('Himachal Travel with Gourav Shrama',styles['Title']),Paragraph('Booking confirmation - not a tax invoice or proof of payment',styles['Heading2'])]
    rows=[('Reference',b['id']),('Status',b['status']),('Guest',b['name']),('Tour',b['tour_name']),('Arrival',b['arrival']),('Travellers',b['people'])]
    for key,label in [('hotel','Hotel'),('hotel_address','Hotel address'),('hotel_phone','Hotel phone'),('pickup','Pickup location'),('pickup_time','Pickup date and time'),('driver','Driver'),('driver_phone','Driver phone'),('vehicle','Vehicle'),('instructions','Guest instructions')]: rows.append((label,b['details'].get(key) or 'To be arranged'))
    p=b['payment']; rows.extend([('Payment',f"{p['currency']} {p['amount']/100:.2f} - {p['status']}" if p else 'No online payment recorded'),('Operator','Gourav Shrama'),('Contact','+91 8091246213'),('Track booking','https://himachal-travel.onrender.com/#track')])
    for label,value in rows:story.extend([Paragraph('<b>'+escape(label)+':</b> '+escape(str(value)).replace('\n','<br/>'),styles['BodyText']),Spacer(1,7)])
    SimpleDocTemplate(buf,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42).build(story);return buf.getvalue()
