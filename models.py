# ==============================================================================
# ملف كلاسات قاعدة البيانات (models.py)
# يحتوي على تعريف جداول وسجلات النظام باستعمال SQLAlchemy ORM
# ==============================================================================

from extensions import db

# ------------------------------------------------------------------------------
# 1. جدول المستخدمين وحسابات الإدارة والصيانة (User)
# ------------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)                        # المعرف الفريد للـ User
    username = db.Column(db.String(100), unique=True, nullable=False)   # اسم المستخدم لدخول الإدارة
    password_hash = db.Column(db.String(255), nullable=False)           # كلمة المرور المشفرة
    role = db.Column(db.String(50), nullable=False)                    # المسمى الوظيفي (Team Leader / Maintenance / Supervisor)
    
    # صلاحيات الحساب
    can_manage_system = db.Column(db.Boolean, default=False)           # صلاحية تعديل النظام (المناطق والألعاب)
    can_manage_areas = db.Column(db.Boolean, default=False)            # (توافق سابق) تعديل المناطق
    can_manage_games = db.Column(db.Boolean, default=False)            # (توافق سابق) تعديل الألعاب
    can_view_reports = db.Column(db.Boolean, default=True)             # صلاحية رؤية الداشبورد والتقارير (متاحة للجميع)

# ------------------------------------------------------------------------------
# 2. جدول المناطق الرئيسية (Area)
# ------------------------------------------------------------------------------
class Area(db.Model):
    __tablename__ = 'areas'
    
    id = db.Column(db.Integer, primary_key=True)                        # المعرف الفريد للمنطقة
    name = db.Column(db.String(100), unique=True, nullable=False)       # اسم المنطقة (مثال: منطقة الترامبولين الرئيسية)
    sort_order = db.Column(db.Integer, default=0)                       # ترتيب ظهور المنطقة (Drag & Drop)
    
    # علاقة الربط بالألعاب (حذف المنطقة يؤدي لحذف ألعابها تلقائياً)
    games = db.relationship('GameModel', backref='area', lazy=True, cascade="all, delete-orphan")

# ------------------------------------------------------------------------------
# 3. جدول الألعاب والمعدات داخل كل منطقة (GameModel)
# ------------------------------------------------------------------------------
class GameModel(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)                        # المعرف الفريد للعبة
    name = db.Column(db.String(100), nullable=False)                    # اسم اللعبة أو المعدة
    area_id = db.Column(db.Integer, db.ForeignKey('areas.id'), nullable=False) # معرف المنطقة التابعة لها
    sort_order = db.Column(db.Integer, default=0)                       # ترتيب ظهور اللعبة للمونيتور (Drag & Drop)
    
    # إعدادات وفلاتر الفحص المخصصة للعبة
    has_map = db.Column(db.Boolean, default=False)                      # هل تحتوي على خريطة موقعية؟
    map_image = db.Column(db.String(255), nullable=True)               # مسار صورة الخريطة الأساسية
    map_mandatory = db.Column(db.Boolean, default=False)               # هل تحديد مكان المشكلة على الخريطة إجباري؟
    allow_photos = db.Column(db.Boolean, default=True)                  # هل يُسمح بإرفاق صور عند وجود عطل؟
    requires_photo = db.Column(db.Boolean, default=False)              # هل إرفاق الصورة إجباري؟
    notes_mandatory = db.Column(db.Boolean, default=False)              # هل كتابة الملاحظات إجبارية؟
    checks = db.Column(db.Text, nullable=False)                         # عناصر وأسئلة الفحص مفرغة بكود JSON

# ------------------------------------------------------------------------------
# 4. جدول تقارير الفحص الميداني المحفوظة (GameReport)
# ------------------------------------------------------------------------------
class GameReport(db.Model):
    __tablename__ = 'game_reports'
    
    id = db.Column(db.Integer, primary_key=True)                        # المعرف الفريد للتقرير
    session_id = db.Column(db.String(100), nullable=False)              # كود الجلسة المجمع للفحص الكلي للمنطقة
    monitor_name = db.Column(db.String(100), nullable=False)            # اسم الموظف المونيتور الذي أجرى الفحص
    area_id = db.Column(db.String(50), nullable=False)                  # اسم/معرف المنطقة
    game_id = db.Column(db.String(50), nullable=False)                  # اسم/معرف اللعبة المفحوصة
    checks_data = db.Column(db.Text, nullable=True)                     # نتائج الأسئلة (سليم/تالف) بصيغة JSON
    notes = db.Column(db.Text, nullable=True)                           # ملاحظات المراقب على اللعبة
    map_image_path = db.Column(db.String(255), nullable=True)          # مسار صورة الخريطة المرسومة بعد التحديد
    photos_paths = db.Column(db.Text, nullable=True)                    # مسارات صور التلفيات والأعطال المرفقة بصيغة JSON
    timestamp = db.Column(db.DateTime, default=db.func.now())           # تاريخ ووقت حفظ التقرير
