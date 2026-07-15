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

# دالة لإنشاء جداول قاعدة البيانات
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
            photos_paths TEXT,     -- مسارات صور الكاميرا محفوظة كـ JSON
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
        # ==========================================
        # --- استراتيجية الحفاظ على الجلسة (Session State) ---
        # بما إننا رفعنا الصور بالـ AJAX، لازم نأكد على السيرفر هنا 
        # إنه ياخد نفس الصور من الـ Session يحطها في الحفظ الجديد 
        # عشان متضيعش وتتمسح لما الموظف يدوس "حفظ والانتقال"
        # ==========================================
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
    if 'monitor_name' not in session or 'area_id' not in session:
        return redirect(url_for('home'))

    monitor_name = session['monitor_name']
    area_id = session['area_id']
    completed_games = session.get('completed_games', [])
    game_data = session.get('game_data', {})

    # إنشاء كود فريد للتقرير بالكامل (عشان التيم ليدر يعرف إن الألعاب دي بتاعت نفس الفحص)
    session_id = uuid.uuid4().hex

    # فتح الاتصال بقاعدة البيانات
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # اللف على كل لعبة الموظف فحصها عشان نسجلها في الجدول
    for game_id in completed_games:
        data = game_data.get(game_id, {})
        
        notes = data.get('notes', '')
        map_drawing = data.get('map_drawing', '')
        photos = data.get('photos', [])
        
        # فصل الاختيارات (check_1, check_2) عن باقي البيانات وحفظها في قاموس منفصل
        checks = {k: v for k, v in data.items() if k.startswith('check_')}
        
        # تحويل القواميس لـ JSON Strings عشان الداتابيز (SQLite) مبتقبلش قواميس مباشرة
        # ensure_ascii=False بتضمن إن الحروف العربي تتخزن صح ومتبقاش رموز غريبة
        checks_json = json.dumps(checks, ensure_ascii=False)
        photos_json = json.dumps(photos, ensure_ascii=False)

        # رمي الداتا جوه الداتابيز
        cursor.execute('''
            INSERT INTO game_reports (session_id, monitor_name, area_id, game_id, checks_data, notes, map_image_path, photos_paths)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, monitor_name, area_id, game_id, checks_json, notes, map_drawing, photos_json))
        
    # تأكيد الحفظ وقفل الاتصال
    conn.commit()
    conn.close()
    
    # بعد الإرسال بنجاح، بنمسح بيانات الفحص من المتصفح عشان يبدأ على نظافة
    session.pop('completed_games', None)
    session.pop('game_data', None)
    session.pop('area_id', None) 

    # شاشة النجاح
    success_html = f"""
    <div style='font-family: Arial; text-align: center; margin-top: 100px; direction: rtl;'>
        <h1 style='color: #28a745;'>تم إرسال تقرير المنطقة بنجاح! 🎉</h1>
        <h3 style='color: #555;'>عاش يا {monitor_name}، شكراً لمجهودك. التقرير اتحفظ في الداتابيز.</h3>
        <br>
        <a href='/' style='padding: 15px 30px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; font-size: 18px;'>العودة للصفحة الرئيسية</a>
    </div>
    """
    return success_html

# مسار لوحة تحكم الإدارة (Dashboard) لعرض التقارير
@app.route('/dashboard', methods=['GET'])
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
# ==========================================
    # --- نظام التنظيف الذكي (Smart Cleanup System) ---
    # بيشتغل أوتوماتيك أول ما أي مدير يفتح الداشبورد
    # بيمسح أي تقرير والصور بتاعته لو عدى عليهم أكتر من 30 يوم
    # عشان الهارد بتاع السيرفر ميتمليش ويوقع السيستم
    # ==========================================    
    cursor.execute("SELECT map_image_path, photos_paths FROM game_reports WHERE timestamp <= datetime('now', '-30 days')")
    old_rows = cursor.fetchall()
    for row in old_rows:
        if row['map_image_path'] and row['map_image_path'].startswith('/static/'):
            fp = row['map_image_path'].lstrip('/')
            if os.path.exists(fp): os.remove(fp)
        if row['photos_paths']:
            try:
                for p in json.loads(row['photos_paths']):
                    if p.startswith('/static/'):
                        fp = p.lstrip('/')
                        if os.path.exists(fp): os.remove(fp)
            except: pass
    cursor.execute("DELETE FROM game_reports WHERE timestamp <= datetime('now', '-30 days')")
    conn.commit()

    # استلام الفلاتر من الرابط
    selected_area = request.args.get('area', '')
    selected_date = request.args.get('date', '')
    selected_monitor = request.args.get('monitor_name', '')

    # تجهيز الاستعلام الأساسي
    query = 'SELECT * FROM game_reports WHERE 1=1'
    params = []
    
    if selected_area:
        query += ' AND area_id = ?'
        params.append(selected_area)
    if selected_date:
        query += ' AND date(timestamp) = ?'
        params.append(selected_date)
    if selected_monitor:
        query += ' AND monitor_name = ?'
        params.append(selected_monitor)
        
    query += ' ORDER BY timestamp DESC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()

    # جلب القوائم للفلترة
    cursor.execute('SELECT DISTINCT area_id FROM game_reports')
    areas = [row['area_id'] for row in cursor.fetchall()]
    
    cursor.execute('SELECT DISTINCT date(timestamp) as rep_date FROM game_reports ORDER BY rep_date DESC')
    dates = [row['rep_date'] for row in cursor.fetchall()]
    
    cursor.execute('SELECT DISTINCT monitor_name FROM game_reports')
    monitors = [row['monitor_name'] for row in cursor.fetchall()]
    
    conn.close()

    grouped_reports = {}
    for row in rows:
        s_id = row['session_id']
        if s_id not in grouped_reports:
            grouped_reports[s_id] = {
                'monitor_name': row['monitor_name'],
                'area_id': row['area_id'],
                'timestamp': row['timestamp'],
                'games': []
            }
        
        checks = json.loads(row['checks_data']) if row['checks_data'] else {}
        photos = json.loads(row['photos_paths']) if row['photos_paths'] else []
        
        game_id = row['game_id']
        game_info = GAMES_CONFIG.get(game_id, {})
        actual_check_names = game_info.get('checks', [])
        base_map = game_info.get('map_image') 
        
        mapped_checks = {}
        for k, v in checks.items():
            if k.startswith('check_'):
                try:
                    idx = int(k.split('_')[1]) - 1
                    name = actual_check_names[idx]
                    mapped_checks[name] = v
                except (IndexError, ValueError):
                    mapped_checks[k] = v
            else:
                mapped_checks[k] = v

        grouped_reports[s_id]['games'].append({
            'game_id': game_id,
            'checks': mapped_checks,
            'notes': row['notes'],
            'map_drawing': row['map_image_path'], 
            'base_map': base_map,                 
            'photos': photos
        })

    return render_template('dashboard.html', reports=grouped_reports, areas=areas, dates=dates, monitors=monitors, selected_area=selected_area, selected_date=selected_date, selected_monitor=selected_monitor)

# مسار تجهيز التقرير للطباعة
@app.route('/print_report/<session_id>')
def print_report(session_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM game_reports WHERE session_id = ?', (session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "التقرير غير موجود"
        
    report = {
        'monitor_name': rows[0]['monitor_name'],
        'area_id': rows[0]['area_id'],
        'timestamp': rows[0]['timestamp'],
        'games': []
    }
    
    for row in rows:
        checks = json.loads(row['checks_data']) if row['checks_data'] else {}
        photos = json.loads(row['photos_paths']) if row['photos_paths'] else []
        game_id = row['game_id']
        game_info = GAMES_CONFIG.get(game_id, {})
        actual_check_names = game_info.get('checks', [])
        base_map = game_info.get('map_image') 
        
        mapped_checks = {}
        for k, v in checks.items():
            if k.startswith('check_'):
                try:
                    idx = int(k.split('_')[1]) - 1
                    name = actual_check_names[idx]
                    mapped_checks[name] = v
                except:
                    mapped_checks[k] = v
            else:
                mapped_checks[k] = v

        report['games'].append({
            'game_id': game_id,
            'checks': mapped_checks,
            'notes': row['notes'],
            'map_drawing': row['map_image_path'], 
            'base_map': base_map,                 
            'photos': photos
        })
        
    return render_template('print_report.html', report=report)

# مسار لحذف تقرير بالكامل (يدوياً)
@app.route('/delete_report/<session_id>', methods=['POST'])
def delete_report(session_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. استخراج مسارات الصور والرسمة عشان نمسحها من الهارد أولاً
    cursor.execute('SELECT map_image_path, photos_paths FROM game_reports WHERE session_id = ?', (session_id,))
    rows = cursor.fetchall()
    
    for row in rows:
        # مسح الرسمة (الخريطة)
        map_path = row['map_image_path']
        if map_path and map_path.startswith('/static/'):
            filepath = map_path.lstrip('/')
            if os.path.exists(filepath):
                os.remove(filepath)
                
        # مسح صور الكاميرا
        photos_json = row['photos_paths']
        if photos_json:
            try:
                photos = json.loads(photos_json)
                for photo in photos:
                    if photo.startswith('/static/'):
                        filepath = photo.lstrip('/')
                        if os.path.exists(filepath):
                            os.remove(filepath)
            except:
                pass

    # 2. مسح التقرير من قاعدة البيانات
    cursor.execute('DELETE FROM game_reports WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('dashboard'))

# نقطة تشغيل السيرفر
if __name__ == '__main__':
    # host='0.0.0.0' تسمح للأجهزة الأخرى على نفس شبكة الواي فاي بالاتصال بالسيرفر
    app.run(host='0.0.0.0', port=5000, debug=True)