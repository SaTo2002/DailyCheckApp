import os
import json
import base64
import uuid
import time
from flask import Blueprint, render_template, request, session, redirect, url_for, current_app
from extensions import db, UPLOAD_FOLDER
from models import Area, GameModel, GameReport

monitor_bp = Blueprint('monitor', __name__)

@monitor_bp.route('/', methods=['GET', 'POST'])
def home():
    try:
        # Clean up unreferenced temporary upload files older than 24 hours
        reports = GameReport.query.with_entities(GameReport.map_image_path, GameReport.photos_paths).all()
        valid_filenames = set()
        for r in reports:
            if r.map_image_path: valid_filenames.add(os.path.basename(r.map_image_path))
            if r.photos_paths:
                for p in json.loads(r.photos_paths): valid_filenames.add(os.path.basename(p))
        current_time = time.time()
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath) and (current_time - os.path.getmtime(filepath)) > 86400:
                if filename not in valid_filenames: os.remove(filepath)
    except Exception as err:
        current_app.logger.warning(f"Error during orphan upload cleanup: {err}")

    if request.method == 'POST':
        session['monitor_name'] = request.form.get('monitor_name')
        selected_area = request.form.get('area')
        session['area_id'] = selected_area 
        session['completed_games'] = []
        session['game_data'] = {}
        return redirect(url_for('monitor.show_games', area_id=selected_area))
    
    areas = Area.query.all()
    return render_template('index.html', areas=areas)

@monitor_bp.route('/games/<area_id>')
def show_games(area_id):
    if 'monitor_name' not in session: return redirect(url_for('monitor.home'))
    area = Area.query.get(area_id)
    if not area: return "هذه المنطقة غير موجودة!"
    games = GameModel.query.filter_by(area_id=area.id).all()
    completed = session.get('completed_games', [])
    all_completed = len(games) > 0 and all(str(g.id) in completed for g in games)
    return render_template('games.html', area_name=area.name, games=games, monitor_name=session['monitor_name'], completed_games=completed, all_completed=all_completed)

@monitor_bp.route('/check/<game_id>', methods=['GET', 'POST'])
def check_game(game_id):
    game = GameModel.query.get(game_id)
    if not game: return "هذه اللعبة غير موجودة في النظام!"
    game_checks = json.loads(game.checks) if game.checks else []
    next_game_id = None
    area_id = session.get('area_id')
    
    if area_id:
        area_games = GameModel.query.filter_by(area_id=area_id).all()
        game_ids = [str(g.id) for g in area_games]
        if game_id in game_ids:
            current_index = game_ids.index(game_id)
            if current_index + 1 < len(game_ids): next_game_id = game_ids[current_index + 1]

    saved_data = session.get('game_data', {}).get(game_id, {})
        
    if request.method == 'POST':
        if 'completed_games' not in session: session['completed_games'] = []
        if game_id not in session['completed_games']: session['completed_games'].append(game_id)
        if 'game_data' not in session: session['game_data'] = {}
            
        current_answers = {}
        for i in range(1, len(game_checks) + 1):
            check_name = f'check_{i}'
            current_answers[check_name] = request.form.get(check_name)
        current_answers['notes'] = request.form.get('notes', '')
        current_answers['photos'] = session.get('game_data', {}).get(game_id, {}).get('photos', [])

        map_drawing_data = request.form.get('map_drawing', '')
        old_map_path = session.get('game_data', {}).get(game_id, {}).get('map_drawing', '')

        if map_drawing_data == '': current_answers['map_drawing'] = ''
        elif map_drawing_data.startswith('data:image'):
            _, encoded = map_drawing_data.split(',', 1)
            filename = f"map_{game_id}_{uuid.uuid4().hex}.png"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, "wb") as fh: fh.write(base64.b64decode(encoded))
            current_answers['map_drawing'] = f"/{filepath}".replace("\\", "/") 
        else: current_answers['map_drawing'] = old_map_path

        session['game_data'][game_id] = current_answers
        session.modified = True
        
        user_action = request.form.get('action')
        if user_action == 'next' and next_game_id: return redirect(url_for('monitor.check_game', game_id=next_game_id))
        else: return redirect(url_for('monitor.show_games', area_id=session.get('area_id')))

    return render_template('form.html', game=game, checks=game_checks, next_game_id=next_game_id, saved_data=saved_data, game_id=game_id)

@monitor_bp.route('/upload_photo_ajax', methods=['POST'])
def upload_photo_ajax():
    game_id = request.form.get('game_id')
    uploaded_files = request.files.getlist('issue_photos')
    new_photos = []
    if 'game_data' not in session: session['game_data'] = {}
    if game_id not in session['game_data']: session['game_data'][game_id] = {}
    if 'photos' not in session['game_data'][game_id]: session['game_data'][game_id]['photos'] = []

    for file in uploaded_files:
        if file and file.filename != '':
            photo_ext = file.filename.split('.')[-1]
            photo_filepath = os.path.join(UPLOAD_FOLDER, f"photo_{game_id}_{uuid.uuid4().hex}.{photo_ext}")
            file.save(photo_filepath)
            photo_url = f"/{photo_filepath}".replace("\\", "/")
            new_photos.append(photo_url)
            session['game_data'][game_id]['photos'].append(photo_url)
    session.modified = True
    return {"status": "success", "photos": new_photos}

@monitor_bp.route('/delete_photo', methods=['POST'])
def delete_photo():
    data = request.json
    game_id = data.get('game_id')
    photo_url = data.get('photo_url')
    if 'game_data' in session and game_id in session['game_data']:
        photos = session['game_data'][game_id].get('photos', [])
        if photo_url in photos:
            photos.remove(photo_url)
            session['game_data'][game_id]['photos'] = photos
            session.modified = True
            if os.path.exists(photo_url.lstrip('/')): os.remove(photo_url.lstrip('/'))
            return {"status": "success"}
    return {"status": "error"}, 400

@monitor_bp.route('/submit_report', methods=['POST'])
def submit_report():
    if 'monitor_name' not in session or 'area_id' not in session: return redirect(url_for('monitor.home'))
    monitor_name, area_id = session['monitor_name'], session['area_id']
    area = Area.query.get(area_id)
    area_name = area.name if area else "منطقة غير معروفة"
    completed_games = session.get('completed_games', [])
    game_data = session.get('game_data', {})
    session_id = uuid.uuid4().hex

    for game_id in completed_games:
        data = game_data.get(game_id, {})
        checks = {k: v for k, v in data.items() if k.startswith('check_')}
        db.session.add(GameReport(
            session_id=session_id, monitor_name=monitor_name, area_id=area_name,
            game_id=game_id, checks_data=json.dumps(checks, ensure_ascii=False),
            notes=data.get('notes', ''), map_image_path=data.get('map_drawing', ''),
            photos_paths=json.dumps(data.get('photos', []), ensure_ascii=False)
        ))
    db.session.commit()
    session.pop('completed_games', None)
    session.pop('game_data', None)
    session.pop('area_id', None) 
    return "<div style='text-align:center; margin-top:100px; direction:rtl;'><h1 style='color:green;'>تم إرسال تقرير المنطقة بنجاح! 🎉</h1><a href='/'>العودة للصفحة الرئيسية</a></div>"

@monitor_bp.route('/cancel_game/<game_id>')
def cancel_game(game_id):
    if game_id in session.get('completed_games', []): return redirect(url_for('monitor.show_games', area_id=session.get('area_id')))
    game_data = session.get('game_data', {}).get(game_id, {})
    for photo in game_data.get('photos', []):
        if os.path.exists(photo.lstrip('/')): os.remove(photo.lstrip('/'))
    map_drawing = game_data.get('map_drawing', '')
    if map_drawing and os.path.exists(map_drawing.lstrip('/')): os.remove(map_drawing.lstrip('/'))
    if 'game_data' in session and game_id in session['game_data']:
        del session['game_data'][game_id]
        session.modified = True
    return redirect(url_for('monitor.show_games', area_id=session.get('area_id')))

@monitor_bp.route('/cancel_area')
def cancel_area():
    for _, data in session.get('game_data', {}).items():
        for photo in data.get('photos', []):
            if os.path.exists(photo.lstrip('/')): os.remove(photo.lstrip('/'))
        map_drawing = data.get('map_drawing', '')
        if map_drawing and os.path.exists(map_drawing.lstrip('/')): os.remove(map_drawing.lstrip('/'))
    session.pop('completed_games', None)
    session.pop('game_data', None)
    session.pop('area_id', None)
    return redirect(url_for('monitor.home'))

@monitor_bp.route('/logout')
def logout():
    cancel_area()
    session.clear()
    return redirect(url_for('monitor.home'))
