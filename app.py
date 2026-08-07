# ==============================================================================
# الملف الرئيسي لتشغيل تطبيق Flask (DailyCheckApp)
# المصمم لإدارة الفحوصات اليومية للمناطق والألعاب
# ==============================================================================

import os
from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import text

# استدعاء كائن قاعدة البيانات الامتدادي والماكينات
from extensions import db
from models import User, Area, GameModel, GameReport

# استدعاء الـ Blueprints مباشرة من حزمة المسارات (routes)
from routes import monitor_bp, admin_bp, manage_bp

# 1. تحميل متغيرات البيئة من ملف .env
load_dotenv()

# 2. إنشاء وتكوين تطبيق فلاسك
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gravity_code_secret_key_fallback')

# إعدادات الاتصال بقاعدة بيانات MySQL
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Max payload upload limit (512 Megabytes to allow high-res canvas Base64 data)
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024

# 3. ربط قاعدة البيانات بتطبيق فلاسك
db.init_app(app)

# 4. تسجيل الـ Blueprints (تقسيم المسارات برمجياً)
app.register_blueprint(monitor_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manage_bp)

@app.context_processor
def inject_language():
    from flask import session
    current_lang = session.get('lang', 'en')
    is_ar = (current_lang == 'ar')
    return {
        'current_lang': current_lang,
        'is_ar': is_ar,
        'dir_attr': 'rtl' if is_ar else 'ltr',
        'html_lang': 'ar' if is_ar else 'en'
    }

# 5. تهيئة جداول قاعدة البيانات والترحيل التلقائي للأعمدة الجديدة (Migrations)
with app.app_context():
    # إنشاء الجداول الأساسية إن لم تكن موجودة
    db.create_all()
    
    # فحص وإضافة أعمدة الصلاحيات الجديدة لجداول المستخدمين إن لم تكن موجودة
    for col, default_val in [('can_manage_system', 0), ('can_manage_areas', 0), ('can_manage_games', 0), ('can_view_reports', 1)]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} TINYINT(1) DEFAULT {default_val}"))
                conn.commit()
        except Exception:
            pass  # العمود موجود بالفعل
            
    # فحص وإضافة عمود ترتيب الألعاب (sort_order) وعمود السماح بالملاحظات (allow_notes) لجداول الألعاب إن لم تكن موجودة
    for col_sql in [
        "ALTER TABLE games ADD COLUMN sort_order INT DEFAULT 0",
        "ALTER TABLE games ADD COLUMN allow_notes TINYINT(1) DEFAULT 1"
    ]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(col_sql))
                conn.commit()
        except Exception:
            pass  # العمود موجود بالفعل

    # فحص وإضافة عمود ترتيب المناطق (sort_order) وعمود اتجاه الـ PDF لجداول المناطق إن لم تكن موجودة
    for col_sql in [
        "ALTER TABLE areas ADD COLUMN sort_order INT DEFAULT 0",
        "ALTER TABLE areas ADD COLUMN pdf_orientation VARCHAR(20) DEFAULT 'portrait'"
    ]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(col_sql))
                conn.commit()
        except Exception:
            pass  # العمود موجود بالفعل

    # فحص وإضافة عمود صورة المنطقة (image) لجداول المناطق إن لم يكن موجوداً
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE areas ADD COLUMN image VARCHAR(255) DEFAULT NULL"))
            conn.commit()
    except Exception:
        pass  # العمود موجود بالفعل

    # إنشاء مجلدات السنة والشهر الحالية تلقائياً في بداية التطبيق والت شهر الجديد
    try:
        from datetime import datetime
        now = datetime.now()
        current_year = now.strftime('%Y')
        current_month = now.strftime('%m')
        pdf_month_folder = os.path.join('pdfs', current_year, current_month)
        os.makedirs(pdf_month_folder, exist_ok=True)
    except Exception:
        pass

# 6. نقطة الانطلاق والتشغيل الخادم المحلي
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)