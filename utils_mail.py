import os
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from extensions import db
from models import EmailLog

def queue_email(subject, body, receiver_emails, attachment_path=None):
    """
    Queue an email for sending in the background.
    """
    if not receiver_emails:
        return False
        
    try:
        email_log = EmailLog(
            subject=subject,
            body=body,
            receiver_emails=json.dumps(receiver_emails, ensure_ascii=False),
            attachment_path=attachment_path,
            status="pending"
        )
        db.session.add(email_log)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error queueing email: {e}")
        db.session.rollback()
        return False

def process_email_queue(app):
    """
    Process pending and failed emails with retry limits.
    Intended to be run in a background thread.
    """
    with app.app_context():
        # Get emails that are pending OR (failed and retry_count < 3 and last_attempt was > 10 mins ago)
        ten_mins_ago = datetime.now() - timedelta(minutes=10)
        
        emails_to_send = EmailLog.query.filter(
            db.or_(
                EmailLog.status == "pending",
                db.and_(
                    EmailLog.status == "failed",
                    EmailLog.retry_count < 3,
                    db.or_(
                        EmailLog.last_attempt_at == None,
                        EmailLog.last_attempt_at <= ten_mins_ago
                    )
                )
            )
        ).all()
        
        if not emails_to_send:
            return
            
        mail_username = os.getenv("MAIL_USERNAME")
        mail_password = os.getenv("MAIL_PASSWORD")
        
        if not mail_username or not mail_password:
            print("Mail credentials missing. Cannot process email queue.")
            return
            
        try:
            # Connect once for all emails if possible, but for stability, connect per email is safer for long running
            for email in emails_to_send:
                # Prepare message
                receivers = json.loads(email.receiver_emails)
                
                msg = MIMEMultipart()
                msg["From"] = mail_username
                msg["To"] = ", ".join(receivers)
                msg["Subject"] = email.subject
                
                final_body = email.body
                if email.retry_count > 0:
                    final_body += "\n\nملاحظة من النظام: هذا الإرسال تم متأخراً عن وقته الأصلي بسبب عطل مؤقت في الاتصال بالإنترنت وقت الفحص."
                    
                msg.attach(MIMEText(final_body, "plain", "utf-8"))
                
                if email.attachment_path and os.path.exists(email.attachment_path):
                    with open(email.attachment_path, "rb") as f:
                        attach_part = MIMEApplication(f.read(), Name=os.path.basename(email.attachment_path))
                    attach_part["Content-Disposition"] = f'attachment; filename="{os.path.basename(email.attachment_path)}"'
                    msg.attach(attach_part)
                
                email.last_attempt_at = datetime.now()
                
                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
                    server.starttls()
                    server.login(mail_username, mail_password)
                    server.send_message(msg)
                    server.quit()
                    
                    email.status = "sent"
                    email.error_message = None
                    db.session.commit()
                except Exception as e:
                    email.status = "failed"
                    email.retry_count += 1
                    email.error_message = str(e)
                    db.session.commit()
                    
        except Exception as e:
            print(f"Queue processing error: {e}")

def send_notification_emails(pdf_path, area_name, date_str, receiver_emails):
    """
    Prepares a report email and queues it.
    """
    subject = f"تقرير فحص جديد - منطقة: {area_name} ({date_str})"
    body = f"""مرحباً،
    
تم للتو الانتهاء من فحص منطقة "{area_name}" بتاريخ {date_str} وتم اعتماد التقرير النهائي.

مرفق طيه ملف الـ PDF الخاص بالتقرير للاطلاع عليه.

مع تحيات،
نظام المراقبة والفحص اليومي
"""
    return queue_email(subject, body, receiver_emails, attachment_path=pdf_path)

def send_negligence_email(area_name, date_str, inspectors_str, completed_count, total_count, receiver_emails):
    """
    Prepares a negligence email and queues it.
    """
    subject = f"🚨 تنبيه إهمال فحص - منطقة: {area_name} ({date_str})"
    body = f"""تحذير إداري،
    
تم رصد جلسة فحص مهملة لم يتم إكمالها وإغلاقها بشكل صحيح.

التفاصيل:
- المنطقة: {area_name}
- تاريخ الجلسة: {date_str}
- المفتشون المتواجدون: {inspectors_str}
- حالة الإنجاز: تم فحص {completed_count} من أصل {total_count} ألعاب فقط قبل ترك الجلسة.

يرجى المتابعة مع فريق التفتيش المذكور.

مع تحيات،
النظام الآلي للمراقبة
"""
    return queue_email(subject, body, receiver_emails)
