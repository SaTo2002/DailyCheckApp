from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
# الكلمة السرية دي ضرورية عشان الـ session يشتغل ويحفظ اسم الموظف
app.secret_key = "gravity_code_secret_key"

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
        
        # توجيهه لصفحة الألعاب الخاصة بالمنطقة اللي اختارها
        return redirect(url_for('show_games', area_id=selected_area))
    
    return render_template('index.html', areas=AREAS_CONFIG)

# مسار جديد لعرض الألعاب بناءً على المنطقة المختارة
@app.route('/games/<area_id>')
def show_games(area_id):
    # حماية: لو الموظف مدخلش اسمه نرجعه للصفحة الرئيسية
    if 'monitor_name' not in session:
        return redirect(url_for('home'))
        
    area_data = AREAS_CONFIG.get(area_id)
    if not area_data:
        return "هذه المنطقة غير موجودة!"
        
    # بنفلتر ونجيب الألعاب اللي تبع المنطقة دي بس
    area_games = {g_id: GAMES_CONFIG[g_id] for g_id in area_data["games"] if g_id in GAMES_CONFIG}
    return render_template('games.html', area_name=area_data["name"], games=area_games, monitor_name=session['monitor_name'])

# مسار الفحص (تم تعديله لمعرفة اللعبة التالية)
@app.route('/check/<game_id>')
def check_game(game_id):
    game_data = GAMES_CONFIG.get(game_id)
    
    if not game_data:
        return "هذه اللعبة غير موجودة في النظام!"

    # --- الكود الجديد: حساب اللعبة اللي عليها الدور ---
    next_game_id = None
    area_id = session.get('area_id') # بنجيب المنطقة بتاعت الموظف
    
    if area_id and area_id in AREAS_CONFIG:
        area_games = AREAS_CONFIG[area_id]['games'] # دي قايمة الألعاب
        if game_id in area_games:
            current_index = area_games.index(game_id) # رقم اللعبة الحالية في القايمة
            # لو اللعبة دي مش آخر لعبة، هات اللي بعدها
            if current_index + 1 < len(area_games):
                next_game_id = area_games[current_index + 1]
    # ------------------------------------------------

    # بنبعت next_game_id للصفحة عشان تعرض الزرار
    return render_template('form.html', game=game_data, next_game_id=next_game_id)

# نقطة تشغيل السيرفر
if __name__ == '__main__':
    # host='0.0.0.0' تسمح للأجهزة الأخرى على نفس شبكة الواي فاي بالاتصال بالسيرفر
    app.run(host='0.0.0.0', port=5000, debug=True)