import os
import sqlite3
import json
import base64
import uuid
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
# الكلمة السرية دي ضرورية عشان الـ session يشتغل
app.secret_key = "gravity_code_secret_key"

# ==========================================
# --- إعدادات قاعدة البيانات ومجلد الصور ---
# ==========================================
DB_NAME = 'gravity_inspections.db'
UPLOAD_FOLDER = os.path.join('static', 'uploads')

# التأكد من وجود مجلد لحفظ الصور عشان لو مش موجود البايثون يعمله أوتوماتيك
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# دالة لإنشاء جداول قاعدة البيانات (هتشتغل مرة واحدة بس أول ما نفتح السيرفر)
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # إنشاء جدول لتقارير الألعاب
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,       -- كود فريد لربط ألعاب نفس التقرير ببعض
            monitor_name TEXT,     -- اسم الموظف
            area_id TEXT,          -- اسم المنطقة
            game_id TEXT,          -- اسم اللعبة
            checks_data TEXT,      -- اختيارات (سليم/مشكلة) محفوظة كـ JSON
            notes TEXT,            -- الملاحظات
            map_image_path TEXT,   -- مسار صورة الرسمة اللي على الخريطة
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # (مستقبلاً هنضيف جدول لصور الكاميرا المتعددة)
    
    conn.commit()
    conn.close()

# تشغيل دالة التأسيس
init_db()
# ==========================================

# قاعدة البيانات المبدئية (قاموس) تحتوي على إعدادات كل لعبة
# أي لعبة جديدة سيتم إضافتها هنا مستقبلاً
GAMES_CONFIG = {
    "Free Jump": {
        "name": "Free Jump",
        "has_map": True, # يحدد إذا كانت اللعبة تحتاج لمخطط رسم أم لا
        "map_image": "free_jump_map.png",  # اسم صورة المخطط في مجلد static
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك", "حالة السجادة (Mat)", "الوسادات (Pad)", "السوست (Spring)"] # عناصر الفحص
    },
    "Performance": {
        "name": "Performance",
        "has_map": True, # يحدد إذا كانت اللعبة تحتاج لمخطط رسم أم لا
        "map_image": "performance_map.png",  # اسم صورة المخطط في مجلد
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك", "حالة السجادة (Mat)", "الوسادات (Pad)", "السوست (Spring)"] # عناصر الفحص
    },
    "Dodge-ball": {
        "name": "Dodge ball",
        "has_map": True, # يحدد إذا كانت اللعبة تحتاج لمخطط رسم أم لا
        "map_image": "Dodge_ball.png",  # اسم صورة المخطط في مجلد static
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك", "حالة السجادة (Mat)", "الوسادات (Pad)", "السوست (Spring)"] # عناصر الفحص
    },
    "Air Bag": {
        "name": "Air Bag",
        "has_map": True, # يحدد إذا كانت اللعبة تحتاج لمخطط رسم أم لا
        "map_image": "Air_Bag.png",  # اسم صورة المخطط في مجلد static
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك", "حالة السجادة (Mat)", "الوسادات (Pad)", "السوست (Spring)"] # عناصر الفحص
    },
    "Ninja-Course": {
        "name": "Ninja Course",
        "has_map": False, # هذه اللعبة لا تحتاج لمخطط رسم
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك"]
    },
    "Zipline": {
        "name": "Zipline",
        "has_map": False, # هذه اللعبة لا تحتاج لمخطط رسم      
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك"]
    },
    "Matrix": {
        "name": "Matrix",
        "has_map": True,          
        "map_image": "matrix_map.png", 
        "checks": ["النظافة", "الإضاءة"]
    },
    "Laser Room": {
        "name": "Laser Room",
        "has_map": False,
        "checks": ["النظافة", "الإضاءة"]
    },
    "Air Track": {
        "name": "Air Track",
        "has_map": False,          
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك"]
    },
    "preparation Area": {
        "name": "Preparation Area",
        "has_map": False,          
        "checks": ["النظافة", "الإضاءة"]
    }
}

# قاموس المناطق (Areas) والألعاب اللي جواها
AREAS_CONFIG = {
    "Park": {
        "name": "Park",
        "games": ["Free Jump", "Performance", "Dodge-ball", "Air Bag", "Ninja-Course", "Zipline", "Matrix", "Laser Room", "Air Track", "preparation Area"] # قائمة الألعاب الموجودة في منطقة البارك
    },
    "Kickzstar": {
        "name": "Kickzstar",
        "games": [] # مكان جاهز لألعاب الترامبولين مستقبلاً
    },
    "Kids-Area": {
        "name": "Kids-Area",
        "games": [] # مكان جاهز لألعاب الأطفال
    },
    "FO": {
        "name": "FO",
        "games": [] # مكان جاهز لمتطلبات الفو
    },
    "Bowling": {
        "name": "Bowling",
        "games": [] # مكان جاهز لألعاب البولينج
    },
    "Lounge": {
        "name": "Lounge",
        "games": [] # مكان جاهز لمتطلبات اللاونج
    }
}

# المسار الرئيسي للموقع (الصفحة الرئيسية)
# مسار شاشة الدخول (إدخال الاسم واختيار المنطقة)
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        # حفظ اسم الموظف والمنطقة لما يدوس دخول
        session['monitor_name'] = request.form.get('monitor_name')
        selected_area = request.form.get('area')
        
        # --- السطر الجديد: حفظ المنطقة في الجلسة عشان نرجع لها بعدين ---
        session['area_id'] = selected_area 
        
        # --- تصفير الألعاب اللي اتفحصت ---
        session['completed_games'] = []
        
        # تصفير بيانات الألعاب المحفوظة لموظف جديد
        session['game_data'] = {}

        # توجيهه لصفحة الألعاب الخاصة بالمنطقة اللي اختارها
        return redirect(url_for('show_games', area_id=selected_area))
    
    return render_template('index.html', areas=AREAS_CONFIG)

# مسار عرض الألعاب بناءً على المنطقة المختارة
@app.route('/games/<area_id>')
def show_games(area_id):
    if 'monitor_name' not in session:
        return redirect(url_for('home'))
        
    area_data = AREAS_CONFIG.get(area_id)
    if not area_data:
        return "هذه المنطقة غير موجودة!"
        
    area_games = {g_id: GAMES_CONFIG[g_id] for g_id in area_data["games"] if g_id in GAMES_CONFIG}
    
    # --- الكود الجديد: حساب الألعاب اللي خلصت ---
    completed = session.get('completed_games', [])
    # بنتأكد إن كل ألعاب المنطقة موجودة في قايمة الألعاب اللي اتفحصت
    all_completed = all(g_id in completed for g_id in area_games.keys())
    # ---------------------------------------------

    # بنبعت حالة الألعاب للصفحة عشان تغير الألوان
    return render_template('games.html', area_name=area_data["name"], games=area_games, monitor_name=session['monitor_name'], completed_games=completed, all_completed=all_completed)

# مسار الفحص (معدل لحفظ الصور في السيرفر وتخفيف الـ Session)
@app.route('/check/<game_id>', methods=['GET', 'POST'])
def check_game(game_id):
    game_data = GAMES_CONFIG.get(game_id)
    if not game_data:
        return "هذه اللعبة غير موجودة في النظام!"

    next_game_id = None
    area_id = session.get('area_id')
    
    if area_id and area_id in AREAS_CONFIG:
        area_games = AREAS_CONFIG[area_id]['games']
        if game_id in area_games:
            current_index = area_games.index(game_id)
            if current_index + 1 < len(area_games):
                next_game_id = area_games[current_index + 1]

    # استرجاع البيانات القديمة لو اللعبة اتفحصت قبل كده
    saved_data = session.get('game_data', {}).get(game_id, {})

    if request.method == 'POST':
        # 1. تسجيل اللعبة في قايمة المنتهين
        if 'completed_games' not in session:
            session['completed_games'] = []
        if game_id not in session['completed_games']:
            session['completed_games'].append(game_id)

        # 2. حفظ إجابات الفورمة (الشيك ليست والملاحظات)
        if 'game_data' not in session:
            session['game_data'] = {}
            
        current_answers = {}
        for i in range(1, len(game_data['checks']) + 1):
            check_name = f'check_{i}'
            current_answers[check_name] = request.form.get(check_name)
        current_answers['notes'] = request.form.get('notes', '')

        # --- الحفاظ على الصور اللي اترفعت في الخلفية (AJAX) ---
        existing_photos = session.get('game_data', {}).get(game_id, {}).get('photos', [])
        current_answers['photos'] = existing_photos
        # --------------------------------------------------

        # ==========================================
        # --- معالجة صورة الرسمة وتوفير مساحة السيرفر ---
        # ==========================================
        map_drawing_data = request.form.get('map_drawing', '')
        old_map_path = session.get('game_data', {}).get(game_id, {}).get('map_drawing', '')

        # 1. لو الموظف داس مسح الكل (البيانات مبعوتة فاضية تماماً)
        if map_drawing_data == '':
            # نمسح الصورة القديمة من الهارد لو موجودة
            if old_map_path and old_map_path.startswith('/static/'):
                filepath = old_map_path.lstrip('/')
                if os.path.exists(filepath):
                    os.remove(filepath)
            current_answers['map_drawing'] = ''
            
        # 2. لو الموظف رسم رسمة جديدة (النص بيبدأ بـ data:image)
        elif map_drawing_data.startswith('data:image'):
            # نمسح الصورة القديمة الأول برضه عشان منراكمش صور لنفس اللعبة
            if old_map_path and old_map_path.startswith('/static/'):
                filepath = old_map_path.lstrip('/')
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
            # حفظ الرسمة الجديدة كملف
            header, encoded = map_drawing_data.split(',', 1)
            filename = f"map_{game_id}_{uuid.uuid4().hex}.png"
            filepath = os.path.join('static', 'uploads', filename)
            
            with open(filepath, "wb") as fh:
                fh.write(base64.b64decode(encoded))
                
            current_answers['map_drawing'] = f"/{filepath}".replace("\\", "/") 
        
        # 3. لو معملش حاجة وملمسش الكانفاس (نحفظ مسار الصورة القديمة زي ما هو)
        else:
            current_answers['map_drawing'] = old_map_path
        # ==========================================

        # حفظ الداتا الجديدة والخفيفة في الـ Session
        session['game_data'][game_id] = current_answers
        session.modified = True
        
        user_action = request.form.get('action')
        
        if user_action == 'next' and next_game_id:
            return redirect(url_for('check_game', game_id=next_game_id))
        else:
            return redirect(url_for('show_games', area_id=session.get('area_id')))

    # إرسال البيانات المحفوظة لملف الـ HTML مع إضافة game_id
    return render_template('form.html', game=game_data, next_game_id=next_game_id, saved_data=saved_data, game_id=game_id)

# مسار مخصص لمسح الصور المحفوظة مؤقتاً
@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    data = request.json
    game_id = data.get('game_id')
    photo_url = data.get('photo_url')
    
    if 'game_data' in session and game_id in session['game_data']:
        photos = session['game_data'][game_id].get('photos', [])
        if photo_url in photos:
            # 1. مسحها من الـ Session
            photos.remove(photo_url)
            session['game_data'][game_id]['photos'] = photos
            session.modified = True
            
            # 2. مسح الملف الفعلي من على الهارد عشان نوفر مساحة
            # بنشيل أول علامة '/' عشان يقرأ المسار صح جوه الفولدر
            filepath = photo_url.lstrip('/')
            if os.path.exists(filepath):
                os.remove(filepath)
                
            return {"status": "success"}
            
    return {"status": "error"}, 400

# مسار مخصص لرفع الصور في الخلفية (AJAX) فور التقاطها
@app.route('/upload_photo_ajax', methods=['POST'])
def upload_photo_ajax():
    game_id = request.form.get('game_id')
    uploaded_files = request.files.getlist('issue_photos')
    new_photos = []

    # التأكد إن اللعبة ليها مكان في الـ Session
    if 'game_data' not in session:
        session['game_data'] = {}
    if game_id not in session['game_data']:
        session['game_data'][game_id] = {}
    if 'photos' not in session['game_data'][game_id]:
        session['game_data'][game_id]['photos'] = []

    for file in uploaded_files:
        if file and file.filename != '':
            photo_ext = file.filename.split('.')[-1]
            photo_filename = f"photo_{game_id}_{uuid.uuid4().hex}.{photo_ext}"
            photo_filepath = os.path.join('static', 'uploads', photo_filename)
            
            # حفظ الصورة
            file.save(photo_filepath)
            
            photo_url = f"/{photo_filepath}".replace("\\", "/")
            new_photos.append(photo_url)
            # إضافتها للـ Session
            session['game_data'][game_id]['photos'].append(photo_url)

    session.modified = True
    return {"status": "success", "photos": new_photos}

# مسار الإرسال النهائي للتقرير
@app.route('/submit_report', methods=['POST'])
def submit_report():
    # حماية: التأكد إن الموظف مسجل الدخول
    if 'monitor_name' not in session:
        return redirect(url_for('home'))

    # (هنا مستقبلاً هنكتب كود حفظ البيانات في الداتابيز أو ملف إكسيل)
    
    # بعد الإرسال بنجاح، بنمسح بيانات الفحص المؤقتة عشان لو حب يفحص منطقة جديدة
    session.pop('completed_games', None)
    session.pop('game_data', None)
    session.pop('area_id', None) # بنمسح المنطقة عشان يختار من الأول

    # شاشة نجاح بسيطة مؤقتة
    success_html = f"""
    <div style='font-family: Arial; text-align: center; margin-top: 100px; direction: rtl;'>
        <h1 style='color: #28a745;'>تم إرسال تقرير المنطقة بنجاح! 🎉</h1>
        <h3 style='color: #555;'>عاش يا {session.get('monitor_name')}، شكراً لمجهودك.</h3>
        <br>
        <a href='/' style='padding: 15px 30px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; font-size: 18px;'>العودة للصفحة الرئيسية</a>
    </div>
    """
    return success_html

# نقطة تشغيل السيرفر
if __name__ == '__main__':
    # host='0.0.0.0' تسمح للأجهزة الأخرى على نفس شبكة الواي فاي بالاتصال بالسيرفر
    app.run(host='0.0.0.0', port=5000, debug=True)