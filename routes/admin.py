# ==============================================================================
# مسارات الإدارة والداشبورد (routes/admin.py)
# مسئول عن: تسجيل دخول الأدمن، تصفح الفحوصات والفلترة، طباعة التقارير، وحذفها
# ==============================================================================

import json
import os
import time
from datetime import date, datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func
from werkzeug.security import check_password_hash

from extensions import MASTER_ADMIN_HASH, db
from models import (
    EmailReceiver,
    GameModel,
    GameReport,
    SystemLog,
    User,
    log_system_event,
)

# إنشاء Blueprint للإدارة والداشبورد
admin_bp = Blueprint("admin", __name__)


# ------------------------------------------------------------------------------
# 1. تسجيل دخول حسابات الإدارة والصيانة (GET & POST)
# ------------------------------------------------------------------------------
@admin_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # 1. التحقق أولاً لو كان الحساب هو Master Admin الرئيسي
        if username == "admin" and check_password_hash(MASTER_ADMIN_HASH, password):
            session["is_admin"] = True
            session["admin_role"] = "admin"
            session["admin_username"] = "Master Admin"
            session["is_master_admin"] = True
            session["can_manage_system"] = True
            session["can_view_reports"] = True
            session["can_delete_reports"] = True
            session["can_view_logs"] = True
            log_system_event("Master Admin", "Admin Login", level="INFO")
            return redirect(url_for("admin.dashboard"))

        # 2. التحقق من الحسابات المسجلة في جدول المستخدمين (users)
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            is_master = user.role == "admin"
            session["is_admin"] = True
            session["admin_username"] = user.username
            session["admin_role"] = user.role
            session["signature_name"] = (
                getattr(user, "signature_name", "") or user.username
            )
            session["is_master_admin"] = is_master
            session["can_view_reports"] = True  # كافة الحسابات يمكنها رؤية الداشبورد
            session["can_manage_system"] = (
                is_master
                or bool(getattr(user, "can_manage_system", False))
                or bool(getattr(user, "can_manage_areas", False))
                or bool(getattr(user, "can_manage_games", False))
            )
            session["can_delete_reports"] = is_master or bool(
                getattr(user, "can_delete_reports", False)
            )
            session["can_view_logs"] = is_master or bool(
                getattr(user, "can_view_logs", False)
            )

            log_system_event(username, "Admin Login", level="INFO")
            return redirect(url_for("admin.dashboard"))

        return render_template(
            "admin_login.html", error="اسم المستخدم أو كلمة المرور غير صحيحة!"
        )
    return render_template("admin_login.html")


# ------------------------------------------------------------------------------
# 2. تسجيل خروج الإدارة وتصفير مفاتيح جلسة الإدارة
# ------------------------------------------------------------------------------
@admin_bp.route("/admin_logout")
def admin_logout():
    admin_name = session.get("admin_username", "Master Admin")
    log_system_event(admin_name, "Admin Logout", level="INFO")
    for k in [
        "is_admin",
        "admin_role",
        "admin_username",
        "is_master_admin",
        "can_manage_system",
        "can_manage_areas",
        "can_manage_games",
        "can_view_reports",
        "can_delete_reports",
        "can_view_logs",
    ]:
        session.pop(k, None)
    return redirect(url_for("monitor.home"))


# ------------------------------------------------------------------------------
# 3. لوحة تحكم الإدارة والداشبورد وعرض تقارير الفحص (GET)
# ------------------------------------------------------------------------------
@admin_bp.route("/dashboard", methods=["GET"])
def dashboard():
    # التحقق من صلاحيات الدخول للداشبورد
    if not session.get("is_admin") or not session.get("can_view_reports"):
        if session.get("is_admin") and session.get("can_manage_system"):
            return redirect(url_for("manage.manage_system"))
        return redirect(url_for("admin.admin_login"))

    # قراءة قيم الفلترة من رابط الرغبات (Query Parameters)
    selected_area = request.args.get("area", "")
    selected_date = request.args.get("date", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    selected_monitor = request.args.get("monitor_name", "")
    status_filter = request.args.get("status_filter", "")  # 'all', 'ok', 'has_issues'
    search_query = request.args.get("search", "").strip()

    # بناء استعلام الفلترة
    query = GameReport.query
    if selected_area:
        query = query.filter(GameReport.area_id == selected_area)
    if selected_date:
        query = query.filter(func.date(GameReport.timestamp) == selected_date)
    if start_date:
        query = query.filter(func.date(GameReport.timestamp) >= start_date)
    if end_date:
        query = query.filter(func.date(GameReport.timestamp) <= end_date)
    if selected_monitor:
        query = query.filter(GameReport.monitor_name == selected_monitor)
    if search_query:
        query = query.filter(
            (GameReport.notes.like(f"%{search_query}%"))
            | (GameReport.area_id.like(f"%{search_query}%"))
            | (GameReport.monitor_name.like(f"%{search_query}%"))
        )

    reports = query.order_by(GameReport.timestamp.desc()).all()

    # جلب القوائم الفرعية المتاحة للفلترة
    areas = [
        r[0] for r in db.session.query(GameReport.area_id).distinct().all() if r[0]
    ]
    dates = [
        str(r[0])
        for r in db.session.query(func.date(GameReport.timestamp)).distinct().all()
        if r[0]
    ]
    monitors = [
        r[0] for r in db.session.query(GameReport.monitor_name).distinct().all() if r[0]
    ]

    from models import ReportApproval

    all_approvals = ReportApproval.query.all()
    approvals_by_session = {}
    for a in all_approvals:
        if a.session_id not in approvals_by_session:
            approvals_by_session[a.session_id] = []
        approvals_by_session[a.session_id].append(
            {
                "admin_name": a.admin_name,
                "role": a.role,
                "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    # تجميع التقارير حسب session_id وحساب الإحصائيات
    grouped_reports = {}
    total_issues_count = 0

    for r in reports:
        if r.session_id not in grouped_reports:
            grouped_reports[r.session_id] = {
                "session_id": r.session_id,
                "monitor_name": r.monitor_name,
                "area_id": r.area_id,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "pdf_file_path": r.pdf_file_path if r.pdf_file_path else "",
                "games": [],
                "has_issues": False,
                "total_checks_count": 0,
                "issue_checks_count": 0,
                "approvals": approvals_by_session.get(r.session_id, []),
            }
        elif r.pdf_file_path and not grouped_reports[r.session_id]["pdf_file_path"]:
            grouped_reports[r.session_id]["pdf_file_path"] = r.pdf_file_path

        game_model = GameModel.query.filter(
            (GameModel.id == r.game_id) | (GameModel.name == r.game_id)
        ).first()
        actual_check_names = (
            [c["name"] for c in json.loads(game_model.checks)]
            if game_model and game_model.checks
            else []
        )
        checks = json.loads(r.checks_data) if r.checks_data else {}

        mapped_checks = {}
        game_has_issue = False

        for k, v in checks.items():
            check_label = k
            if k.startswith("check_"):
                try:
                    idx = int(k.split("_")[1]) - 1
                    check_label = (
                        actual_check_names[idx] if idx < len(actual_check_names) else k
                    )
                except Exception:
                    check_label = k

            is_ok = v == "سليم" or v == "OK"
            mapped_checks[check_label] = "OK" if is_ok else "NOK"

            grouped_reports[r.session_id]["total_checks_count"] += 1
            if not is_ok:
                game_has_issue = True
                total_issues_count += 1
                grouped_reports[r.session_id]["issue_checks_count"] += 1

        if game_has_issue:
            grouped_reports[r.session_id]["has_issues"] = True

        grouped_reports[r.session_id]["games"].append(
            {
                "game_id": game_model.name if game_model else r.game_id,
                "checks": mapped_checks,
                "has_issue": game_has_issue,
                "notes": r.notes,
                "map_drawing": r.map_image_path,
                "base_map": game_model.map_image if game_model else "",
                "photos": json.loads(r.photos_paths) if r.photos_paths else [],
            }
        )

    # فلترة حسب حالة الفحص (كل الجلسة سليمة ✅ vs بها أعطال ❌)
    if status_filter == "ok":
        grouped_reports = {
            sid: rep for sid, rep in grouped_reports.items() if not rep["has_issues"]
        }
    elif status_filter == "has_issues":
        grouped_reports = {
            sid: rep for sid, rep in grouped_reports.items() if rep["has_issues"]
        }

    # جلب الجلسات المهملة لعرضها في قسم خاص
    # (الجلسات التي تم تعيينها كـ abandoned سواء يدوياً أو تلقائياً بواسطة قبل الطلب)

    from models import Area, DailySession

    neglected_sessions = []
    # نجلب الجلسات المهجورة، وخصوصا التي تم التبليغ عنها أو المهجورة بشكل عام (بدون تقارير)
    abandoned = (
        DailySession.query.filter_by(status="abandoned")
        .order_by(DailySession.date.desc())
        .limit(20)
        .all()
    )
    for ds in abandoned:
        # تأكد أنها لا تمتلك تقارير مكتملة في grouped_reports
        # (رغم أن المهجورة لا تُكتمل أبداً)
        area = db.session.get(Area, ds.area_id)

        try:
            inspectors = (
                json.loads(ds.active_inspectors) if ds.active_inspectors else []
            )
        except Exception:
            inspectors = []

        try:
            game_data = json.loads(ds.game_data) if ds.game_data else {}
        except Exception:
            game_data = {}

        total_count = GameModel.query.filter_by(area_id=ds.area_id).count()
        completed_count = len(game_data)

        # إذا كانت الجلسة فارغة تماماً (لم يتم فحص أي لعبة)، نقوم بحذفها ولا نعرضها
        if completed_count == 0:
            db.session.delete(ds)
            db.session.commit()
            continue

        progress_pct = int(
            (completed_count / total_count * 100) if total_count > 0 else 0
        )

        neglected_sessions.append(
            {
                "session_id": ds.id,
                "area_name": area.name if area else ds.area_id,
                "date": ds.date.strftime("%Y-%m-%d"),
                "inspectors": inspectors,
                "progress_pct": progress_pct,
                "completed_count": completed_count,
                "total_count": total_count,
                "reported": ds.negligence_reported,
            }
        )

    # Check if the admin needs to set their signature
    needs_signature = False
    if session.get("admin_role") and session.get("admin_role") not in [
        "Admin",
        "Supervisor",
    ]:
        if not session.get("signature_name"):
            needs_signature = True

    return render_template(
        "dashboard.html",
        reports=grouped_reports,
        neglected_sessions=neglected_sessions,
        areas=areas,
        dates=dates,
        monitors=monitors,
        selected_area=selected_area,
        selected_date=selected_date,
        start_date=start_date,
        end_date=end_date,
        selected_monitor=selected_monitor,
        status_filter=status_filter,
        search_query=search_query,
        needs_signature=needs_signature,
    )


# ------------------------------------------------------------------------------
# Profile
# ------------------------------------------------------------------------------
@admin_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))
    

    admin_username = session.get("admin_username")
    user = User.query.filter_by(username=admin_username).first()

    if not user:
        if admin_username == "Master Admin" or session.get("is_master_admin"):

            class DummyUser:
                username = "Master Admin"
                role = "admin"
                signature_name = session.get("signature_name", "")

            user = DummyUser()
        else:
            return redirect(url_for("admin.admin_login"))

    if request.method == "POST":
        signature_name = request.form.get("signature_name", "").strip()
        if signature_name:
            if hasattr(user, "id"):  # If it's a real database user
                user.signature_name = signature_name
                db.session.commit()
            session["signature_name"] = signature_name
        return redirect(url_for("admin.profile"))

    return render_template("profile.html", user=user)


# ------------------------------------------------------------------------------
# Pending Approvals
# ------------------------------------------------------------------------------
@admin_bp.route("/pending_approvals")
def pending_approvals():
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))

    admin_role = session.get("admin_role")
    admin_username = session.get("admin_username")

    if not admin_role or admin_role in ["Admin", "Supervisor"]:
        return redirect(url_for("admin.dashboard"))

    from models import GameReport, ReportApproval

    all_reports = (
        GameReport.query.order_by(GameReport.timestamp.desc()).limit(200).all()
    )
    pending_reports = []
    seen_sessions = set()

    time

    today = datetime.now().date()

    for report in all_reports:
        if report.session_id in seen_sessions:
            continue
        seen_sessions.add(report.session_id)

        approvals = ReportApproval.query.filter_by(session_id=report.session_id).all()
        report.approvals = approvals

        already_signed_by_me = any(
            app.admin_username == admin_username for app in approvals
        )
        if already_signed_by_me:
            continue

        if admin_role == "Team Leader":
            tl_approvals = [
                app
                for app in approvals
                if app.role in ["Team Leader AM", "Team Leader PM"]
            ]
            report_date = report.timestamp.date()

            if not tl_approvals:
                pending_reports.append(report)
            else:
                if report_date == today:
                    pending_reports.append(report)
                else:
                    continue
        else:
            role_signed = any(app.role == admin_role for app in approvals)
            if not role_signed:
                pending_reports.append(report)

    return render_template("pending_approvals.html", pending_reports=pending_reports)


# ------------------------------------------------------------------------------
# API for Live Sync Dashboard
# ------------------------------------------------------------------------------
@admin_bp.route("/api/admin_dashboard_sync", methods=["GET"])
def api_admin_dashboard_sync():
    if not session.get("is_admin") or not session.get("can_view_reports"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    from models import DailySession, GameReport

    latest_report = GameReport.query.order_by(GameReport.id.desc()).first()
    latest_report_id = latest_report.id if latest_report else None
    reports_count = GameReport.query.count()

    latest_ns = (
        DailySession.query.filter_by(status="in_progress")
        .order_by(DailySession.id.desc())
        .first()
    )
    latest_ns_id = latest_ns.id if latest_ns else None
    ns_count = DailySession.query.filter_by(status="in_progress").count()

    return jsonify(
        {
            "status": "ok",
            "reports_count": reports_count,
            "latest_report_id": latest_report_id,
            "neglected_count": ns_count,
            "latest_ns_id": latest_ns_id,
        }
    )


# ------------------------------------------------------------------------------
# 4. طباعة التقرير المجمع for Area (GET)
# ------------------------------------------------------------------------------
@admin_bp.route("/print_report/<session_id>")
def print_report(session_id):
    if not session.get("is_admin") or not session.get("can_view_reports"):
        return redirect(url_for("admin.admin_login"))
    reports = GameReport.query.filter_by(session_id=session_id).all()
    if not reports:
        return "التقرير غير موجود"

    report_data = {
        "session_id": session_id,
        "monitor_name": reports[0].monitor_name,
        "area_id": reports[0].area_id,
        "timestamp": reports[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "games": [],
    }

    for r in reports:
        game_model = GameModel.query.filter(
            (GameModel.id == r.game_id) | (GameModel.name == r.game_id)
        ).first()
        actual_check_names = (
            [c["name"] for c in json.loads(game_model.checks)]
            if game_model and game_model.checks
            else []
        )
        mapped_checks = {}
        for k, v in (json.loads(r.checks_data) if r.checks_data else {}).items():
            if k.startswith("check_"):
                try:
                    mapped_checks[
                        (
                            actual_check_names[int(k.split("_")[1]) - 1]
                            if int(k.split("_")[1]) - 1 < len(actual_check_names)
                            else k
                        )
                    ] = ("OK" if (v == "سليم" or v == "OK") else "NOK")
                except Exception:
                    mapped_checks[k] = v
            else:
                mapped_checks[k] = v
        report_data["games"].append(
            {
                "game_id": game_model.name if game_model else r.game_id,
                "checks": mapped_checks,
                "notes": r.notes,
                "map_drawing": r.map_image_path,
                "base_map": (
                    game_model.map_image.replace("/static/", "").lstrip("/")
                    if game_model and game_model.map_image
                    else ""
                ),
                "photos": json.loads(r.photos_paths) if r.photos_paths else [],
            }
        )
    return render_template("print_report.html", report=report_data)


@admin_bp.route("/view_neglected/<int:session_id>")
def view_neglected(session_id):
    if not session.get("is_admin") or not session.get("can_view_reports"):
        return redirect(url_for("admin.admin_login"))

    import json

    from models import Area, DailySession

    ds = db.get_or_404(DailySession, session_id)
    area = db.session.get(Area, ds.area_id)

    report_data = {
        "session_id": session_id,
        "monitor_name": (
            " / ".join(json.loads(ds.active_inspectors))
            if ds.active_inspectors
            else "Unknown"
        ),
        "area_id": area.name if area else ds.area_id,
        "timestamp": ds.date.strftime("%Y-%m-%d") + " (Incomplete)",
        "games": [],
    }

    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    for game_id, checks in game_data.items():
        game_model = GameModel.query.filter(
            (GameModel.id == game_id) | (GameModel.name == game_id)
        ).first()
        actual_check_names = (
            [c["name"] for c in json.loads(game_model.checks)]
            if game_model and game_model.checks
            else []
        )
        mapped_checks = {}
        for k, v in checks.items():
            if k.startswith("check_"):
                try:
                    mapped_checks[
                        (
                            actual_check_names[int(k.split("_")[1]) - 1]
                            if int(k.split("_")[1]) - 1 < len(actual_check_names)
                            else k
                        )
                    ] = ("OK" if (v == "سليم" or v == "OK") else "NOK")
                except Exception:
                    mapped_checks[k] = v
            elif k not in ["notes", "photos", "inspector_name", "map_drawing"]:
                mapped_checks[k] = v

        report_data["games"].append(
            {
                "game_id": game_model.name if game_model else game_id,
                "checks": mapped_checks,
                "notes": checks.get("notes", ""),
                "map_drawing": checks.get("map_drawing", ""),
                "base_map": (
                    game_model.map_image.replace("/static/", "").lstrip("/")
                    if game_model and game_model.map_image
                    else ""
                ),
                "photos": checks.get("photos", []),
            }
        )

    return render_template("neglected_report.html", report=report_data)


@admin_bp.route("/delete_neglected/<int:session_id>", methods=["POST"])
def delete_neglected(session_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))

    from models import DailySession

    ds = db.get_or_404(DailySession, session_id)
    log_system_event(
        session.get("admin_username", "Master Admin"),
        "Delete Neglected Session",
        details=f"Deleted neglected session #{session_id} for Area ID: {ds.area_id}",
        level="WARNING",
    )
    db.session.delete(ds)
    db.session.commit()
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/reopen_neglected/<int:session_id>")
def reopen_neglected(session_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))

    from models import DailySession

    ds = db.get_or_404(DailySession, session_id)
    log_system_event(
        session.get("admin_username", "Master Admin"),
        "Reopen Neglected Session",
        details=f"Reopened neglected session #{session_id} for Area ID: {ds.area_id}",
        level="INFO",
    )
    # Reset status and date so it appears to monitors today
    ds.status = "in_progress"
    ds.date = date.today()
    ds.negligence_reported = False
    db.session.commit()
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/force_complete_neglected/<int:session_id>")
def force_complete_neglected(session_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))

    import json

    from models import DailySession, GameModel, GameReport

    ds = db.get_or_404(DailySession, session_id)
    log_system_event(
        session.get("admin_username", "Master Admin"),
        "Force Complete Neglected Session",
        details=f"Forced complete for session #{session_id}, Area ID: {ds.area_id}",
        level="WARNING",
    )

    try:
        game_data = json.loads(ds.game_data) if ds.game_data else {}
    except Exception:
        game_data = {}

    area_games = GameModel.query.filter_by(area_id=ds.area_id).all()
    monitor_name = "الإدارة (إجبار إنهاء)"
    if ds.active_inspectors:
        try:
            inspectors = json.loads(ds.active_inspectors)
            if inspectors:
                monitor_name = " / ".join(inspectors)
        except Exception:
            pass

    for game in area_games:
        game_key = str(game.id)
        if game_key not in game_data and game.name not in game_data:
            # Create a missing entry
            try:
                checks = json.loads(game.checks) if game.checks else []
            except Exception:
                checks = []

            missing_checks = {}
            for i, _ in enumerate(checks):
                missing_checks[f"check_{i+1}"] = "N/A"
            missing_checks["notes"] = "لم يتم الفحص (تم الإنهاء بواسطة الإدارة)"
            missing_checks["photos"] = []
            missing_checks["map_drawing"] = ""

            game_data[game_key] = missing_checks

    import uuid

    report_uuid = uuid.uuid4().hex

    for game_id_or_name, data in game_data.items():
        # Clean up data keys
        checks_only = {
            k: v
            for k, v in data.items()
            if k not in ["notes", "photos", "inspector_name", "map_drawing"]
        }
        notes = data.get("notes", "").strip() or "N/A"
        photos = data.get("photos", [])
        map_drawing = data.get("map_drawing", "")

        # Determine actual game ID string
        game_model = GameModel.query.filter(
            (GameModel.id == game_id_or_name) | (GameModel.name == game_id_or_name)
        ).first()
        final_game_id = game_model.name if game_model else game_id_or_name

        report = GameReport(
            session_id=report_uuid,
            monitor_name=monitor_name,
            area_id=ds.area_id,
            game_id=final_game_id,
            checks_data=json.dumps(checks_only, ensure_ascii=False),
            photos_paths=json.dumps(photos, ensure_ascii=False),
            map_image_path=map_drawing,
            notes=notes,
        )
        db.session.add(report)

    ds.status = "completed"
    db.session.commit()

    # Generate PDF
    try:
        from pdf_generator import generate_pdf_report

        generate_pdf_report(report_uuid)
    except Exception as e:
        print(f"Error generating PDF: {e}")

    return redirect(url_for("admin.dashboard"))


# ------------------------------------------------------------------------------
# 6. تصدير وعرض وتنزيل تقرير الـ PDF المترجم من Excel
# ------------------------------------------------------------------------------
@admin_bp.route("/download_pdf/<session_id>")
def download_pdf(session_id):
    if not session.get("is_admin") or not session.get("can_view_reports"):
        return redirect(url_for("admin.admin_login"))

    is_view = request.args.get("view") == "1"

    # 1. القراءة الفورية O(1) للمسار المسجل في قاعدة البيانات
    pdf_file_path = None
    rep = GameReport.query.filter_by(session_id=session_id).first()

    if rep and rep.pdf_file_path and os.path.exists(rep.pdf_file_path):
        pdf_file_path = rep.pdf_file_path
    else:
        # لو الملف مش موجود في المسار المسجل (أو بيتم توليده حالياً بالخلفية)، نفحص المسار المتوقع أو ننتظر ثواني معدودة
        if rep:
            year_folder = rep.timestamp.strftime("%Y")
            month_folder = rep.timestamp.strftime("%m")
            ddmmyy_date = rep.timestamp.strftime("%d%m%y")
            branch_code = os.getenv("BRANCH_CODE", "alm").lower().strip()
            area_folder_name = (
                "".join(
                    [
                        c if c.isalnum() or c in (" ", "_", "-") else ""
                        for c in rep.area_id
                    ]
                ).strip()
                or "General"
            )

            expected_filename = f"{ddmmyy_date}_{branch_code}_{session_id[:6]}.pdf"
            direct_path = os.path.abspath(
                os.path.join(
                    "pdfs",
                    year_folder,
                    month_folder,
                    area_folder_name,
                    expected_filename,
                )
            )

            for _ in range(
                10
            ):  # محاولة فحص المسار المباشر إن كان التقرير يتولد حالياً بالخلفية
                if os.path.exists(direct_path):
                    pdf_file_path = direct_path
                    # تحديث المسار بجدول الداتابيز للإلحاق السريع بالمستقبل
                    rep.pdf_file_path = direct_path
                    db.session.commit()
                    break
                time.sleep(0.5)

    # 2. إن لم يكن الملف موجوداً على الجهاز إطلاقاً (أو اتمسح من القرص)، نقوم بإعادة توليده فوراً وتحديث الداتابيز
    if not pdf_file_path or not os.path.exists(pdf_file_path):
        try:
            from pdf_generator import generate_report_excel_and_pdf

            _, pdf_file_path = generate_report_excel_and_pdf(session_id)
        except Exception as e:
            return f"حدث خطأ أثناء توليد ملف الـ PDF: {str(e)}", 500

    # 3. إرسال الملف للمستخدم (عرض أو تحميل) مع منع التخزين المؤقت (Cache)
    if pdf_file_path and os.path.exists(pdf_file_path):
        from flask import send_file, make_response

        response = make_response(
            send_file(
                pdf_file_path,
                as_attachment=not is_view,
                download_name=os.path.basename(pdf_file_path),
                mimetype="application/pdf",
            )
        )
        # Prevent caching on mobile browsers so updated signatures always show
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
    else:
        return "لم يتم العثور على ملف الـ PDF المعني.", 404


# ------------------------------------------------------------------------------
# 5. حذف التقرير يدوياً وتنظيف صوره نهائياً من النظام (POST)
# ------------------------------------------------------------------------------
@admin_bp.route("/delete_report/<session_id>", methods=["POST"])
def delete_report(session_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))
    if not session.get("can_delete_reports"):
        flash("عذراً، لا تملك صلاحية حذف التقارير.", "danger")
        return redirect(url_for("admin.dashboard"))

    log_system_event(
        session.get("admin_username", "Master Admin"),
        "Delete Report",
        details=f"Deleted report for session: {session_id}",
        level="WARNING",
    )

    for r in GameReport.query.filter_by(session_id=session_id).all():
        if r.map_image_path and os.path.exists(r.map_image_path.lstrip("/")):
            filename = os.path.basename(r.map_image_path)
            # Protect base maps and cover images (either by filename prefix or by folder path)
            if (
                not filename.startswith("base_map_")
                and not filename.startswith("area_cover_")
                and "/maps/" not in r.map_image_path
            ):
                try:
                    os.remove(r.map_image_path.lstrip("/"))
                except Exception:
                    pass

        if r.photos_paths:
            try:
                for p in json.loads(r.photos_paths):
                    if os.path.exists(p.lstrip("/")):
                        os.remove(p.lstrip("/"))
            except Exception:
                pass
        db.session.delete(r)

    # Delete cached PDF file across subfolders on server disk
    try:
        for root, dirs, files in os.walk("pdfs"):
            for file in files:
                if session_id[:6] in file or session_id in file:
                    os.remove(os.path.join(root, file))
    except Exception:
        pass

    db.session.commit()
    return redirect(url_for("admin.dashboard"))


# ------------------------------------------------------------------------------
# 6. إدارة القائمة البريدية (Email Receivers)
# ------------------------------------------------------------------------------
@admin_bp.route("/manage_emails")
def manage_emails():
    if not session.get("is_admin") or not session.get("can_manage_system"):
        return redirect(url_for("admin.dashboard"))
    receivers = EmailReceiver.query.all()
    return render_template("manage_emails.html", receivers=receivers)


@admin_bp.route("/add_email", methods=["POST"])
def add_email():
    if not session.get("is_admin") or not session.get("can_manage_system"):
        return redirect(url_for("admin.dashboard"))
    name = request.form.get("name")
    email = request.form.get("email")
    if name and email:
        new_rcv = EmailReceiver(name=name, email=email)
        db.session.add(new_rcv)
        db.session.commit()
    return redirect(url_for("admin.manage_emails"))


@admin_bp.route("/toggle_email/<int:rcv_id>")
def toggle_email(rcv_id):
    if not session.get("is_admin") or not session.get("can_manage_system"):
        return redirect(url_for("admin.dashboard"))
    rcv = db.session.get(EmailReceiver, rcv_id)
    if rcv:
        rcv.is_active = not rcv.is_active
        db.session.commit()
    return redirect(url_for("admin.manage_emails"))


@admin_bp.route("/delete_email/<int:rcv_id>", methods=["POST"])
def delete_email(rcv_id):
    if not session.get("is_admin") or not session.get("can_manage_system"):
        return redirect(url_for("admin.dashboard"))
    rcv = db.session.get(EmailReceiver, rcv_id)
    if rcv:
        log_system_event(
            session.get("admin_username", "Master Admin"),
            "Delete Email",
            details=f"Deleted Email: {rcv.email}",
            level="WARNING",
        )
        db.session.delete(rcv)
        db.session.commit()
    return redirect(url_for("admin.manage_emails"))


@admin_bp.route("/system_logs")
def system_logs():
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))
    if not session.get("is_master_admin") and not session.get("can_view_logs"):
        return redirect(url_for("admin.dashboard"))

    logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).all()
    return render_template("system_logs.html", logs=logs)


# ------------------------------------------------------------------------------
# 11. سجل الإيميلات (Email Logs)
# ------------------------------------------------------------------------------
@admin_bp.route("/email_logs")
def email_logs():
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))
    if not session.get("is_master_admin") and not session.get("can_view_logs"):
        return redirect(url_for("admin.dashboard"))

    from models import EmailLog

    logs = EmailLog.query.order_by(EmailLog.id.desc()).all()
    return render_template("email_logs.html", logs=logs)


@admin_bp.route("/retry_failed_emails", methods=["POST"])
def retry_failed_emails():
    if not session.get("is_admin") or not session.get("is_master_admin"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        import threading

        from flask import current_app

        from extensions import db

        # Reset retry limits for failed emails before running
        from models import EmailLog
        from utils_mail import process_email_queue

        failed_logs = EmailLog.query.filter_by(status="failed").all()
        count = len(failed_logs)
        for log in failed_logs:
            log.retry_count = 0  # reset to allow retry
            log.last_attempt_at = None
        db.session.commit()

        log_system_event(
            session.get("admin_username", "Master Admin"),
            "Retry Failed Emails",
            details=f"Triggered manual retry for {count} failed emails",
            level="INFO",
        )

        # Start background thread
        app_obj = current_app._get_current_object()
        threading.Thread(target=process_email_queue, args=(app_obj,)).start()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------------------------
# 12. اعتماد التقرير من قبل الإدارة (POST)
# ------------------------------------------------------------------------------
@admin_bp.route("/approve_report/<session_id>", methods=["POST"])
def approve_report(session_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login"))

    from models import ReportApproval

    admin_username = session.get("admin_username")
    admin_name = session.get("signature_name")
    role = session.get("admin_role")
    source = request.form.get("source", "dashboard")

    if not admin_name:
        flash(
            "You must set your signature name in your profile before approving.",
            "danger",
        )
        return redirect(url_for("admin.profile"))

    # If Supervisor or Admin, they don't sign Excel, but shouldn't really be approving anyway.
    if role in ["Supervisor", "Admin"]:
        flash("You do not have a signing role.", "danger")
        return redirect(url_for("admin.dashboard"))
    if role == "Team Leader":
        shift = request.form.get("shift", "AM")
        role = f"Team Leader {shift}"

    if admin_name and role:
        # Check if already approved by this exact username on this report
        existing = ReportApproval.query.filter_by(
            session_id=session_id, admin_username=admin_username
        ).first()
        if existing:
            flash("You have already approved this report.", "warning")
            if source == "pending":
                return redirect(url_for("admin.pending_approvals"))
            return redirect(url_for("admin.dashboard"))

        new_app = ReportApproval(
            session_id=session_id,
            admin_username=admin_username,
            admin_name=admin_name,
            role=role,
        )
        db.session.add(new_app)
        db.session.commit()

        # Regenerate PDF in background to include new signature
        import os
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

    return redirect(url_for("admin.dashboard"))
