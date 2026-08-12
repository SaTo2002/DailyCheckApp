import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

def send_notification_emails(pdf_path, area_name, date_str, receiver_emails):
    """
    Sends an email to a list of receivers with the generated PDF attached.
    """
    mail_username = os.getenv('MAIL_USERNAME')
    mail_password = os.getenv('MAIL_PASSWORD')
    
    if not mail_username or not mail_password:
        print("Mail credentials not found in .env")
        return False
        
    if not receiver_emails:
        print("No active receivers found.")
        return False

    subject = f"تقرير فحص جديد - منطقة: {area_name} ({date_str})"
    
    body = f"""
    مرحباً،
    
    تم للتو الانتهاء من فحص منطقة "{area_name}" بتاريخ {date_str} وتم اعتماد التقرير النهائي.
    
    مرفق طيه ملف الـ PDF الخاص بالتقرير للاطلاع عليه.
    
    مع تحيات،
    نظام المراقبة والفحص اليومي
    """
    
    msg = MIMEMultipart()
    msg['From'] = mail_username
    msg['To'] = ", ".join(receiver_emails)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Attach the PDF
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            attach_part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
        attach_part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
        msg.attach(attach_part)
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
