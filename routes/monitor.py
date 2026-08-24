# ==============================================================================
# مسارات المراقب والفحص الميداني (routes/monitor.py)
# مسئول عن: تسجيل المونيتور، اختيار المنطقة، فحص الألعاب، رفع الصور، وإرسال التقارير
# ==============================================================================

import base64
import json
import os
import time
import uuid
from datetime import date

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from extensions import UPLOAD_FOLDER, db
from models import (
    Area,
    DailySession,
    GameModel,
    GameReport,
    SystemLog,
    log_system_event,
)

# إنشاء Blueprint للمراقب
monitor_bp = Blueprint("monitor", __name__)


# ------------------------------------------------------------------------------
# 1. الصفحة الرئيسية للمونيتور لتسجيل الاسم واختيار المنطقة (GET & POST)
# ------------------------------------------------------------------------------
@monitor_bp.route("/", methods=["GET", "POST"])
def home():
    try:
        # --- آلية التنظيف الآلي للصور المهملة (أكبر من 24 ساعة) ---
        # 1. جمع قائمة بالصور المحمية التابعة لتقارير مسجلة أو خرائط أساسية أو أغلفة المناطق
        reports = GameReport.query.with_entities(
            GameReport.map_image_path, GameReport.photos_paths
        ).all()
        games = GameModel.query.with_entities(GameModel.map_image).all()
        areas = Area.query.with_entities(Area.image).all()

        valid_filenames = {".gitkeep"}
        for r in reports:
            if r.map_image_path:
                valid_filenames.add(os.path.basename(r.map_image_path))
            if r.photos_paths:
                try:
                    for p in json.loads(r.photos_paths):
                        valid_filenames.add(os.path.basename(p))
                except Exception:
                    pass
        for g in games:
            if g.map_image:
                valid_filenames.add(os.path.basename(g.map_image))
        for a in areas:
            if a.image:
                valid_filenames.add(os.path.basename(a.image))

        # 2. تنظيف الصور المؤقتة المهملة فقط من مجلدي drawings و photos (المستقلين تماماً عن maps و covers)
        current_time = time.time()
        for subfolder in ["drawings", "photos"]:
            target_dir = os.path.join(UPLOAD_FOLDER, subfolder)
            if os.path.exists(target_dir):
                for filename in os.listdir(target_dir):
                    filepath = os.path.join(target_dir, filename)
                    if (
                        os.path.isfile(filepath)
                        and (current_time - os.path.getmtime(filepath)) > 86400
                    ):
                        if filename not in valid_filenames:
                            try:
                                os.remove(filepath)
                            except Exception:
                                pass
    except Exception as err:
        current_app.logger.warning(f"Error during orphan upload cleanup: {err}")

    if request.method == "POST":
        monitor_name = request.form.get("monitor_name")
        session["monitor_name"] = monitor_name
        selected_area = request.form.get("area")
        session["area_id"] = selected_area
        
        area_obj = db.session.get(Area, selected_area)
        area_name = area_obj.name if area_obj else selected_area
        
        log_system_event(
            monitor_name,
            "Monitor Area Login",
            details=f"Entered Area: {area_name}",
            level="INFO",
        )
        return redirect(url_for("monitor.show_games", area_id=selected_area))

    areas = Area.query.order_by(Area.sort_order.asc(), Area.id.asc()).all()
    return render_template("index.html", areas=areas)


@monitor_bp.route("/reset_and_start", methods=["POST"])
def reset_and_start():
    monitor_name = request.form.get("monitor_name")
    selected_area = request.form.get("area")

    session["monitor_name"] = monitor_name
    session["area_id"] = selected_area

    ds = DailySession.query.filter_by(
        area_id=str(selected_area), date=date.today(), status="in_progress"
    ).first()
    
    area_obj = db.session.get(Area, selected_area)
    area_name = area_obj.name if area_obj else selected_area
    
    if ds:
        db.session.delete(ds)
        db.session.commit()
        log_system_event(
            monitor_name,
            "Cancel Old Session & Start New",
            details=f"Area: {area_name}",
            level="WARNING",
        )
    else:
        log_system_event(
            monitor_name,
            "Monitor Area Login",
            details=f"Entered Area: {area_name}",
            level="INFO",
        )

    return redirect(url_for("monitor.show_games", area_id=selected_area))


# ------------------------------------------------------------------------------
# 2. عرض قائمة الألعاب التابعة for Area المختارة بترتيبها المخصص (GET)
# ------------------------------------------------------------------------------
@monitor_bp.route("/games/<area_id>")
def show_games(area_id):
    if "monitor_name" not in session:
        return redirect(url_for("monitor.home"))
    monitor_name = session["monitor_name"]
    area = db.session.get(Area, area_id)
    if not area:
        return "هذه المنطقة غير موجودة!"
        
    # === NEW: Split Area Locking Logic ===
    if area.name.lower() in ["park", "f.o", "lounge"]:
        completed_ds = DailySession.query.filter_by(
            area_id=str(area.id), date=date.today(), status="completed"
        ).first()
        if completed_ds:
            try:
                active_inspectors = json.loads(completed_ds.active_inspectors) if completed_ds.active_inspectors else []
                inspector_name = ", ".join(active_inspectors) if active_inspectors else "Another Inspector"
            except Exception:
                inspector_name = "Another Inspector"
                
            colored_name = f"<span style='color: #e4006c; font-weight: 800;'>{inspector_name}</span>"
            flash(f"The {area.name} check has already been completed by {colored_name}. Please wait for the rest of the group to finish.", "warning")
            return redirect(url_for("monitor.home"))

    # 1. إغلاق الجلسات المعلقة من الأيام السابقة لنفس المنطقة
    old_sessions = DailySession.query.filter(
        DailySession.area_id == str(area.id),
        DailySession.status == "in_progress",
        DailySession.date < date.today(),
    ).all()
    for osess in old_sessions:
        osess.status = "abandoned"
    if old_sessions:
        db.session.commit()

    # 2. البحث عن جلسة اليوم أو إنشاء واحدة جديدة
    ds = DailySession.query.filter_by(
        area_id=str(area.id), date=date.today(), status="in_progress"
    ).first()

    if not ds:
        ds = DailySession(area_id=str(area.id), date=date.today(), status="in_progress")
        db.session.add(ds)
        db.session.commit()

    # 3. تحديث قائمة المفتشين النشطين
    try:
        active_inspectors = (
            json.loads(ds.active_inspectors) if ds.active_inspectors else []
        )
    except Exception:
        active_inspectors = []

    if monitor_name not in active_inspectors:
        active_inspectors.append(monitor_name)
        ds.active_inspectors = json.dumps(active_inspectors, ensure_ascii=False)
        db.session.commit()

    # 4. جلب الألعاب المكتملة والأقفال
    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    try:
        game_locks = json.loads(ds.game_locks) if ds.game_locks else {}
        keys_to_delete = [k for k, v in game_locks.items() if v == monitor_name and not str(k).startswith("__heartbeat_")]
        if keys_to_delete:
            for k in keys_to_delete:
                del game_locks[k]
            ds.game_locks = json.dumps(game_locks, ensure_ascii=False)
            db.session.commit()
            
        # Filter out heartbeats for the template so JS doesn't infinitely reload
        game_locks = {k: v for k, v in game_locks.items() if not str(k).startswith("__heartbeat_")}
    except Exception:
        game_locks = {}

    games = (
        GameModel.query.filter_by(area_id=area.id)
        .order_by(GameModel.sort_order.asc(), GameModel.id.asc())
        .all()
    )
    completed = list(game_data.keys())
    all_completed = len(games) > 0 and all(str(g.id) in completed for g in games)
    cancel_flag = request.args.get("cancel")

    if len(games) == 1 and not all_completed and not cancel_flag:
        return redirect(url_for("monitor.check_game", game_id=games[0].id))

    return render_template(
        "games.html",
        games=games,
        area_name=area.name,
        completed_games=completed,
        game_data=game_data,
        game_locks=game_locks,
        monitor_name=monitor_name,
        all_completed=all_completed,
        active_inspectors=active_inspectors,
        ds_id=ds.id,
    )


# ------------------------------------------------------------------------------
# 3. صفحة فحص لعبة معينة (نموذج الأسئلة والخريطة والصور) (GET & POST)
# ------------------------------------------------------------------------------


def _get_next_game_id(area_id, current_game_id):
    if not area_id:
        return None
    area_games = (
        GameModel.query.filter_by(area_id=area_id)
        .order_by(GameModel.sort_order.asc(), GameModel.id.asc())
        .all()
    )
    game_ids = [str(g.id) for g in area_games]
    if current_game_id in game_ids:
        current_index = game_ids.index(current_game_id)
        if current_index + 1 < len(game_ids):
            return game_ids[current_index + 1]
    return None


def _process_map_drawing(map_drawing_data, game, old_map_path):
    if map_drawing_data == "":
        return game.map_image if game and game.map_image else ""

    if map_drawing_data.startswith("data:image"):
        if old_map_path and old_map_path.startswith("/static/uploads/drawings/"):
            old_file_on_disk = old_map_path.lstrip("/")
            if os.path.exists(old_file_on_disk):
                try:
                    os.remove(old_file_on_disk)
                except Exception:
                    pass

        _, encoded = map_drawing_data.split(",", 1)
        filename = f"map_{game.id}_{uuid.uuid4().hex}.png"
        drawings_dir = os.path.join(UPLOAD_FOLDER, "drawings")
        os.makedirs(drawings_dir, exist_ok=True)
        filepath = os.path.join(drawings_dir, filename)
        img_bytes = base64.b64decode(encoded)

        try:
            import io

            from PIL import Image

            image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            image.save(filepath, "PNG", optimize=True)
        except Exception:
            with open(filepath, "wb") as fh:
                fh.write(img_bytes)

        return f"/{filepath}".replace("\\", "/")

    return (
        old_map_path
        if old_map_path
        else (game.map_image if game and game.map_image else "")
    )


@monitor_bp.route("/check/<game_id>", methods=["GET", "POST"])
def check_game(game_id):
    if "monitor_name" not in session:
        return redirect(url_for("monitor.home"))
    monitor_name = session["monitor_name"]

    game = db.session.get(GameModel, game_id)
    if not game:
        return "هذه اللعبة غير موجودة في النظام!"

    area_id = session.get("area_id")
    if not area_id:
        return redirect(url_for("monitor.home"))

    ds = DailySession.query.filter_by(
        area_id=str(area_id), date=date.today(), status="in_progress"
    ).first()
    if not ds:
        return redirect(url_for("monitor.show_games", area_id=area_id))

    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    game_checks = json.loads(game.checks) if game.checks else []
    next_game_id = _get_next_game_id(area_id, game_id)
    saved_data = game_data.get(str(game_id), {})

    area_games_count = (
        GameModel.query.filter_by(area_id=area_id).count() if area_id else 0
    )
    single_game_mode = area_games_count == 1

    # Restrict editing to the original inspector who saved it
    if saved_data:
        original_inspector = saved_data.get("inspector_name")
        if original_inspector and original_inspector != monitor_name:
            # Allow viewing but not editing - render read-only view
            return render_template(
                "form.html",
                game=game,
                checks=game_checks,
                next_game_id=next_game_id,
                saved_data=saved_data,
                game_id=game_id,
                single_game_mode=single_game_mode,
                read_only=True,
                read_only_inspector=original_inspector,
            )


    if request.method == "POST":
        current_answers = {}
        for i in range(1, len(game_checks) + 1):
            check_val = request.form.get(f"check_{i}")
            current_answers[f"check_{i}"] = check_val
            # Save comment only if NOK is selected to keep data clean
            if check_val == "NOK" or check_val == "تالف/يوجد مشكلة":
                current_answers[f"comment_{i}"] = request.form.get(f"comment_{i}", "").strip()
            else:
                current_answers[f"comment_{i}"] = ""
        current_answers["notes"] = request.form.get("notes", "")
        current_answers["photos"] = saved_data.get("photos", [])
        current_answers["inspector_name"] = monitor_name

        old_map_path = saved_data.get("map_drawing", "")
        current_answers["map_drawing"] = _process_map_drawing(
            request.form.get("map_drawing", ""), game, old_map_path
        )

        is_edit = str(game_id) in game_data
        game_data[str(game_id)] = current_answers
        ds.game_data = json.dumps(game_data, ensure_ascii=False)

        # تحرير القفل فوراً بعد حفظ الإجابات لتسريع العمل
        try:
            game_locks = json.loads(ds.game_locks) if ds.game_locks else {}
            if str(game_id) in game_locks:
                del game_locks[str(game_id)]
            ds.game_locks = json.dumps(game_locks, ensure_ascii=False)
        except Exception:
            pass

        db.session.commit()

        log_msg = "Edit Game Inspection" if is_edit else "Submit Game Inspection"
        log_system_event(
            monitor_name, log_msg, details=f"Game: {game.name}", level="INFO"
        )

        user_action = request.form.get("action")
        if user_action == "submit_report":
            return redirect(url_for("monitor.submit_report"))
        elif user_action == "next" and next_game_id:
            return redirect(url_for("monitor.check_game", game_id=next_game_id))
        else:
            return redirect(url_for("monitor.show_games", area_id=area_id))

    # GET request - check and set lock
    try:
        game_locks = json.loads(ds.game_locks) if ds.game_locks else {}
    except Exception:
        game_locks = {}

    # Prevent entry if locked by someone else (Unless override is requested)
    override = request.args.get("override")
    if str(game_id) in game_locks and game_locks[str(game_id)] != monitor_name:
        if override != "1":
            return redirect(url_for("monitor.show_games", area_id=area_id))
        else:
            log_system_event(
                monitor_name,
                "Override Game Lock",
                details=f"Game: {game.name} - Locked previously by {game_locks[str(game_id)]}",
                level="WARNING",
            )

    # Clear any existing locks for THIS user on OTHER games
    keys_to_delete = [
        k for k, v in game_locks.items() if v == monitor_name and k != str(game_id)
    ]
    for k in keys_to_delete:
        del game_locks[k]

    game_locks[str(game_id)] = monitor_name
    ds.game_locks = json.dumps(game_locks, ensure_ascii=False)
    db.session.commit()

    return render_template(
        "form.html",
        game=game,
        checks=game_checks,
        next_game_id=next_game_id,
        saved_data=saved_data,
        game_id=game_id,
        single_game_mode=single_game_mode,
    )


# ------------------------------------------------------------------------------
# 4. رفع صور التلفيات عبر AJAX (POST) مع ضغط الحجم التلقائي
# ------------------------------------------------------------------------------
@monitor_bp.route("/upload_photo_ajax", methods=["POST"])
def upload_photo_ajax():
    game_id = request.form.get("game_id")
    area_id = session.get("area_id")
    uploaded_files = request.files.getlist("issue_photos")
    new_photos = []

    ds = DailySession.query.filter_by(
        area_id=str(area_id), date=date.today(), status="in_progress"
    ).first()
    if not ds:
        return {"status": "error", "message": "No active session"}, 400

    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    if str(game_id) not in game_data:
        game_data[str(game_id)] = {}
    if "photos" not in game_data[str(game_id)]:
        game_data[str(game_id)]["photos"] = []

    for file in uploaded_files:
        if file and file.filename != "":
            photos_dir = os.path.join(UPLOAD_FOLDER, "photos")
            os.makedirs(photos_dir, exist_ok=True)
            photo_filepath = os.path.join(
                photos_dir, f"photo_{game_id}_{uuid.uuid4().hex}.jpg"
            )

            try:
                from PIL import Image

                img = Image.open(file).convert("RGB")
                # Resize if image is huge (> 1600px width/height)
                img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                img.save(photo_filepath, "JPEG", quality=80, optimize=True)
            except Exception:
                file.save(photo_filepath)

            photo_url = f"/{photo_filepath}".replace("\\", "/")
            new_photos.append(photo_url)
            game_data[str(game_id)]["photos"].append(photo_url)

    ds.game_data = json.dumps(game_data, ensure_ascii=False)
    db.session.commit()
    return {"status": "success", "photos": new_photos}


# ------------------------------------------------------------------------------
# 5. حذف صورة مرفوعة أثناء المعاينة (POST)
# ------------------------------------------------------------------------------
@monitor_bp.route("/delete_photo", methods=["POST"])
def delete_photo():
    data = request.json
    game_id = data.get("game_id")
    photo_url = data.get("photo_url")
    area_id = session.get("area_id")

    ds = DailySession.query.filter_by(
        area_id=str(area_id), date=date.today(), status="in_progress"
    ).first()
    if not ds:
        return {"status": "error", "message": "No active session"}, 400

    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    if str(game_id) in game_data:
        photos = game_data[str(game_id)].get("photos", [])
        if photo_url in photos:
            photos.remove(photo_url)
            game_data[str(game_id)]["photos"] = photos
            ds.game_data = json.dumps(game_data, ensure_ascii=False)
            db.session.commit()
            if os.path.exists(photo_url.lstrip("/")):
                os.remove(photo_url.lstrip("/"))
            return {"status": "success"}
    return {"status": "error"}, 400


# ------------------------------------------------------------------------------
# 6. إرسال تقرير المنطقة النهائي وحفظه نهائياً في قاعدة البيانات (GET & POST)
# ------------------------------------------------------------------------------
def _needs_signature(ds, monitor_name):
    # Signature is now automatically taken from the monitor's name
    return False

# ------------------------------------------------------------------------------
@monitor_bp.route("/submit_report", methods=["GET", "POST"])
def submit_report():
    if "monitor_name" not in session or "area_id" not in session:
        return redirect(url_for("monitor.home"))
    monitor_name, area_id = session["monitor_name"], session["area_id"]
    area = db.session.get(Area, area_id)
    area_name = area.name if area else "منطقة غير معروفة"

    ds = DailySession.query.filter_by(
        area_id=str(area_id), date=date.today(), status="in_progress"
    ).first()
    if not ds:
        return redirect(url_for("monitor.show_games", area_id=area_id))

    try:
        active_inspectors = json.loads(ds.active_inspectors) if ds.active_inspectors else [monitor_name]
    except Exception:
        active_inspectors = [monitor_name]

    # Auto-assign signatures using the monitor's name
    try:
        signatures = json.loads(ds.monitor_signatures) if ds.monitor_signatures else {}
    except Exception:
        signatures = {}
        
    for inspector in active_inspectors:
        if inspector not in signatures or not signatures[inspector].strip():
            signatures[inspector] = inspector
    ds.monitor_signatures = json.dumps(signatures, ensure_ascii=False)
    db.session.commit()

    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    completed_games = list(game_data.keys())
    
    # === NEW: Shared session_id for split areas ===
    is_split = area and area.name.lower() in ["park", "f.o", "lounge"]
    if is_split:
        split_areas_db = Area.query.filter(Area.name.in_(["Park", "F.O", "Lounge"])).all()
        split_area_ids_for_index = [str(a.id) for a in split_areas_db]
        
        exported_count = DailySession.query.filter(
            DailySession.area_id.in_(split_area_ids_for_index),
            DailySession.date == date.today(),
            DailySession.status == "exported"
        ).count()
        
        group_index = (exported_count // len(split_area_ids_for_index)) + 1
        session_id = f"split_{date.today().strftime('%Y%m%d')}_{group_index}"
    else:
        session_id = uuid.uuid4().hex

    # 1. جلب كافة ألعاب المنطقة لضمان تسجيل التقرير لجميع ألعاب المنطقة
    area_games = (
        GameModel.query.filter_by(area_id=area.id).all()
        if area
        else GameModel.query.all()
    )

    # حفظ سجل تقرير فرعي لكل لعبة في المنطقة
    for gm in area_games:
        game_id_str = str(gm.id)
        data = game_data.get(game_id_str, {})
        checks = {k: v for k, v in data.items() if k.startswith("check_") or k.startswith("comment_")}

        actual_inspector = data.get("inspector_name", monitor_name)

        # الافتراضي دائماً: صورة الخريطة الأصلية من قاعدة البيانات (لو اللعبة عندها ماب)
        base_map = (gm.map_image or "").strip()
        final_map_path = base_map if (gm.has_map and base_map) else ""

        # لو المونيتور رسم على الخريطة فعلاً
        user_drawing = data.get("map_drawing", "") or ""
        is_real_drawing = (
            user_drawing
            and user_drawing != base_map
            and "/uploads/" in user_drawing
            and "map_" in user_drawing
            and os.path.exists(user_drawing.lstrip("/"))
        )
        if is_real_drawing:
            final_map_path = user_drawing

        db.session.add(
            GameReport(
                session_id=session_id,
                monitor_name=actual_inspector,
                area_id=area_name,
                game_id=game_id_str,
                checks_data=json.dumps(checks, ensure_ascii=False),
                notes=data.get("notes", "").strip() or "N/A",
                map_image_path=final_map_path,
                photos_paths=json.dumps(data.get("photos", []), ensure_ascii=False),
                monitor_signatures=ds.monitor_signatures,
            )
        )

    ds.status = "completed"
    db.session.commit()

    # === NEW: Wait for all 3 split areas logic ===
    if is_split:
        # Get IDs of all 3 split areas
        split_areas_db = Area.query.filter(Area.name.in_(["Park", "F.O", "Lounge"])).all()
        split_area_ids = [str(a.id) for a in split_areas_db]
        
        # Count how many are completed TODAY (including the one we just saved)
        completed_sessions = DailySession.query.filter(
            DailySession.area_id.in_(split_area_ids),
            DailySession.date == date.today(),
            DailySession.status == "completed"
        ).all()
        
        if len(completed_sessions) < len(split_area_ids):
            # Not all are done. Skip PDF generation.
            log_system_event(
                monitor_name,
                "Area Report Completed (Waiting for Group)",
                details=f"Area: {area.name}, Completed {len(completed_sessions)}/{len(split_area_ids)}",
                level="INFO",
            )
            games_count = len(completed_games)
            session.pop("area_id", None)
            
            return render_template(
                "report_success.html",
                area_name=area_name,
                monitor_name=monitor_name,
                games_count=games_count,
            )
            
        # If all 3 are done, mark them all as exported and proceed to PDF generation
        for s in completed_sessions:
            s.status = "exported"
        db.session.commit()

    # 2. إنشاء وتصدير ملف الـ PDF تلقائياً في العملية الخلفية
    log_system_event(
        monitor_name,
        "Generate Area Report",
        details=f"Area: {area.name} (Split Group Complete)" if is_split else f"Area: {area.name}, Games inspected: {len(completed_games)}",
        level="INFO",
    )

    import subprocess
    import sys

    cmd = [
        sys.executable,
        "-c",
        f"from dotenv import load_dotenv; load_dotenv(); from app import app; app.app_context().push(); from pdf_generator import generate_report_excel_and_pdf; generate_report_excel_and_pdf('{session_id}')",
    ]
    subprocess.Popen(
        cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )

    games_count = len(completed_games)
    session.pop("area_id", None)

    return render_template(
        "report_success.html",
        area_name=area_name,
        monitor_name=monitor_name,
        games_count=games_count,
    )


# ------------------------------------------------------------------------------
# 7. إلغاء فحص لعبة محددة وتنظيف ملفاتها غير المحفوظة
# ------------------------------------------------------------------------------
@monitor_bp.route("/cancel_game/<game_id>")
def cancel_game(game_id):
    area_id = session.get("area_id")
    ds = DailySession.query.filter_by(
        area_id=str(area_id), date=date.today(), status="in_progress"
    ).first()
    if not ds:
        return redirect(url_for("monitor.show_games", area_id=area_id))

    try:
        game_locks = json.loads(ds.game_locks) if ds.game_locks else {}
        if str(game_id) in game_locks:
            del game_locks[str(game_id)]
            ds.game_locks = json.dumps(game_locks, ensure_ascii=False)
            db.session.commit()
    except Exception:
        pass

    return redirect(url_for("monitor.show_games", area_id=area_id))


# ------------------------------------------------------------------------------
# 8. إلغاء فحص المنطقة بالكامل (خروج المفتش أو تصفير الجلسة)
# ------------------------------------------------------------------------------
@monitor_bp.route("/cancel_area")
def cancel_area():
    area_id = session.get("area_id")
    monitor_name = session.get("monitor_name")
    reset_all = request.args.get("reset")

    if area_id:
        ds = DailySession.query.filter_by(
            area_id=str(area_id), date=date.today(), status="in_progress"
        ).first()
        
        if ds:
            if reset_all == "1":
                db.session.delete(ds)
                
                area_obj = db.session.get(Area, area_id)
                area_name = area_obj.name if area_obj else area_id
                
                log_system_event(
                    monitor_name or "Unknown",
                    "Cancel Area Inspection (Reset)",
                    details=f"Area: {area_name}",
                    level="WARNING",
                )
            elif monitor_name:
                if request.path == "/cancel_area":
                    area_obj = db.session.get(Area, area_id)
                    area_name = area_obj.name if area_obj else area_id
                    log_system_event(
                        monitor_name,
                        "Save Progress & Exit",
                        details=f"Exited Area: {area_name}",
                        level="INFO",
                    )

                try:
                    active_inspectors = (
                        json.loads(ds.active_inspectors) if ds.active_inspectors else []
                    )
                    if monitor_name in active_inspectors:
                        active_inspectors.remove(monitor_name)
                        ds.active_inspectors = json.dumps(
                            active_inspectors, ensure_ascii=False
                        )
                except Exception:
                    active_inspectors = []

                try:
                    game_locks = json.loads(ds.game_locks) if ds.game_locks else {}
                    keys_to_delete = [
                        k for k, v in game_locks.items() if v == monitor_name
                    ]
                    for k in keys_to_delete:
                        del game_locks[k]
                    ds.game_locks = json.dumps(game_locks, ensure_ascii=False)
                except Exception:
                    pass
                    
                # Auto-delete session if no one is left and no games were saved
                try:
                    game_data_check = json.loads(ds.game_data) if ds.game_data else {}
                except Exception:
                    game_data_check = {}
                    
                if len(active_inspectors) == 0 and len(game_data_check) == 0:
                    db.session.delete(ds)

            db.session.commit()

    session.pop("area_id", None)
    return redirect(url_for("monitor.home"))


# ------------------------------------------------------------------------------
# 9. API لجلب حالة الجلسة الحالية (Live Sync)
# ------------------------------------------------------------------------------
@monitor_bp.route("/api/session_status/<area_id>")
def api_session_status(area_id):
    import time
    
    ds = DailySession.query.filter_by(
        area_id=str(area_id), date=date.today(), status="in_progress"
    ).first()
    
    # === NEW: Split Area Locking Logic ===
    area = db.session.get(Area, area_id)
    if area and area.name.lower() in ["park", "f.o", "lounge"]:
        completed_ds = DailySession.query.filter_by(
            area_id=str(area_id), date=date.today(), status="completed"
        ).first()
        if completed_ds:
            try:
                active_inspectors = json.loads(completed_ds.active_inspectors) if completed_ds.active_inspectors else []
                inspector_name = ", ".join(active_inspectors) if active_inspectors else "Another Inspector"
            except Exception:
                inspector_name = "Another Inspector"
            
            colored_name = f"<span style='color: #e4006c; font-weight: 800;'>{inspector_name}</span>"
            return {
                "status": "locked_split",
                "message": f"The {area.name} check has already been completed by {colored_name}. Please wait for the other areas in the group (Park, F.O, Lounge) to finish."
            }
            
    if not ds:
        return {"status": "no_session"}

    monitor_name = session.get("monitor_name")

    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    try:
        game_locks = json.loads(ds.game_locks) if ds.game_locks else {}
    except Exception:
        game_locks = {}

    try:
        active_inspectors = (
            json.loads(ds.active_inspectors) if ds.active_inspectors else []
        )
    except Exception:
        active_inspectors = []

    changed = False
    now_ts = int(time.time())

    # 1. Update heartbeat for current user
    if monitor_name:
        heartbeat_key = f"__heartbeat_{monitor_name}"
        game_locks[heartbeat_key] = now_ts
        changed = True

    # 2. Check for stale users (inactive for more than 15 seconds)
    stale_users = []
    for ins in list(active_inspectors):
        hb_key = f"__heartbeat_{ins}"
        last_ping = game_locks.get(hb_key)
        if last_ping is None:
            game_locks[hb_key] = now_ts
            changed = True
        else:
            try:
                if now_ts - int(last_ping) > 15:
                    stale_users.append(ins)
            except:
                pass

    for su in stale_users:
        if su in active_inspectors:
            active_inspectors.remove(su)
            changed = True
        
        keys_to_delete = [k for k, v in game_locks.items() if v == su]
        for k in keys_to_delete:
            del game_locks[k]
            changed = True
            
        if f"__heartbeat_{su}" in game_locks:
            del game_locks[f"__heartbeat_{su}"]
            changed = True
            
        log_system_event(
            su,
            "Auto-Logout (Inactive)",
            details="User closed browser or lost connection",
            level="WARNING"
        )

    if changed:
        ds.active_inspectors = json.dumps(active_inspectors, ensure_ascii=False)
        ds.game_locks = json.dumps(game_locks, ensure_ascii=False)
        db.session.commit()

    completed_games = list(game_data.keys())
    clean_locks = {k: v for k, v in game_locks.items() if not str(k).startswith("__heartbeat_")}

    return {
        "status": "ok",
        "completed_games": completed_games,
        "game_locks": clean_locks,
        "active_inspectors": active_inspectors,
    }


# ------------------------------------------------------------------------------
# 10. تسجيل خروج المراقب وتصفير الجلسة
# ------------------------------------------------------------------------------
@monitor_bp.route("/logout")
def logout():
    monitor_name = session.get("monitor_name")
    area_id = session.get("area_id")
    
    if monitor_name:
        log_system_event(
            monitor_name,
            "Monitor Logout",
            details="-",
            level="INFO",
        )
    cancel_area()
    session.clear()
    return redirect(url_for("monitor.home"))
