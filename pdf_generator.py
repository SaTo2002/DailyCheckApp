import json
import os
import shutil
import subprocess
import tempfile

import openpyxl


def generate_report_excel_and_pdf(session_id):
    """
    يقوم بتصدير تقرير الـ Excel في مجلد مؤقت،
    ثم يحوله فوراً إلى ملف PDF في مجلد pdfs/YYYY/MM/Area/
    ويمسح ملف الـ Excel المؤقت فور الانتهاء.
    يرجع (None, pdf_path).
    """
    from models import GameModel, GameReport

    reports = GameReport.query.filter_by(session_id=session_id).all()
    if not reports:
        return None, None

    if session_id.startswith("split_"):
        area_name = "Park"
    else:
        area_name = reports[0].area_id

    # حساب الشخص الذي قام بأكبر عدد من الفحوصات (قاعدة الأغلبية)
    inspector_counts = {}
    for r in reports:
        inspector_counts[r.monitor_name] = inspector_counts.get(r.monitor_name, 0) + 1

    main_monitor_name = (
        max(inspector_counts, key=inspector_counts.get)
        if inspector_counts
        else reports[0].monitor_name
    )
    monitor_name = main_monitor_name

    monitor_signatures_dict = {}
    for r in reports:
        if getattr(r, 'monitor_signatures', None):
            sig_dict = json_loads(r.monitor_signatures)
            if isinstance(sig_dict, dict):
                monitor_signatures_dict.update(sig_dict)
                
    monitor_signature_text = " و ".join(list(monitor_signatures_dict.values())) if monitor_signatures_dict else monitor_name

    ts = reports[0].timestamp
    date_str = ts.strftime("%Y-%m-%d")

    from models import ReportApproval
    approvals = ReportApproval.query.filter_by(session_id=session_id).all()

    game_checks = {}
    game_notes = {}
    game_maps = {}

    for r in reports:
        game_model = GameModel.query.filter(
            (GameModel.id == r.game_id) | (GameModel.name == r.game_id)
        ).first()
        game_name = game_model.name if game_model else r.game_id

        actual_check_names = (
            [c["name"] for c in json_loads(game_model.checks)]
            if game_model and game_model.checks
            else []
        )
        checks_dict = {}
        parsed_checks = json_loads(r.checks_data) if r.checks_data else {}
        for k, v in parsed_checks.items():
            if k.startswith("check_"):
                try:
                    q_idx = int(k.split("_")[1])
                    q_title = (
                        actual_check_names[q_idx - 1]
                        if q_idx - 1 < len(actual_check_names)
                        else k
                    )
                    status_val = "OK" if (v == "سليم" or v == "OK") else "NOK"
                    comment_val = parsed_checks.get(f"comment_{q_idx}", "")
                    checks_dict[q_title] = {"status": status_val, "comment": comment_val}
                except Exception:
                    checks_dict[k] = {"status": v, "comment": ""}
            elif not k.startswith("comment_"):
                checks_dict[k] = v

        game_checks[game_name] = checks_dict

        # إضافة اسم المفتش الفعلي للملاحظات إذا كان مختلفاً عن المفتش الرئيسي
        final_notes = r.notes.strip() if r.notes else ""
        if final_notes.upper() == "N/A":
            final_notes = ""
            
        if r.monitor_name != main_monitor_name:
            inspector_note = f"تم الفحص بواسطة: ({r.monitor_name})"
            final_notes = (
                f"{inspector_note} - {final_notes}" if final_notes else inspector_note
            )

        if final_notes:
            game_notes[game_name] = final_notes

        base_map_path = (
            game_model.map_image.lstrip("/")
            if game_model and game_model.map_image
            else ""
        )

        if r.map_image_path:
            game_maps[game_name] = {"drawing": r.map_image_path, "base": base_map_path}
        elif base_map_path:
            game_maps[game_name] = {"drawing": "", "base": base_map_path}

    year_folder = ts.strftime("%Y")
    month_folder = ts.strftime("%m")
    ddmmyy_date = ts.strftime("%d%m%y")

    # كود الفرع: يُقرأ من ملف .env — يتغير فقط لو فتحنا فرع جديد
    branch_code = os.getenv("BRANCH_CODE", "alm").lower().strip()

    # تنظيف اسم المنطقة لاستخدامه كمجلد مستقل (مثل: Park, Kids, Kickerz, Bowling)
    area_folder_name = "".join(
        [c if c.isalnum() or c in (" ", "_", "-") else "" for c in area_name]
    ).strip()
    if not area_folder_name:
        area_folder_name = "General"

    # مجلد الـ PDF الدائم فقط: (pdfs / السنة / الشهر / اسم_المنطقة)
    pdf_dir = os.path.join("pdfs", year_folder, month_folder, area_folder_name)
    os.makedirs(pdf_dir, exist_ok=True)

    file_basename = f"{ddmmyy_date}_{branch_code}_{session_id[:6]}"
    pdf_path = os.path.abspath(os.path.join(pdf_dir, f"{file_basename}.pdf"))

    # مجلد مؤقت للـ xlsx فقط — يُمسح تلقائياً بعد التحويل
    temp_dir = tempfile.mkdtemp()
    xlsx_path = os.path.abspath(os.path.join(temp_dir, f"{file_basename}.xlsx"))

    # قراءة اتجاه طباعة المنطقة المحدد من قاعدة البيانات
    from models import Area

    area_obj = Area.query.filter(
        (Area.name == area_name) | (Area.name.like(f"%{area_name}%"))
    ).first()
    orientation = (
        area_obj.pdf_orientation
        if area_obj and area_obj.pdf_orientation
        else "portrait"
    )

    # 1. تصدير ملف الـ Excel المحلي
    from excel_exporter import export_report_to_excel

    export_report_to_excel(
        report_session_id=session_id,
        monitor_name=main_monitor_name,
        area_name=area_name,
        checks_dict=game_checks,
        game_notes_dict=game_notes,
        game_maps_dict=game_maps,
        date_str=date_str,
        output_xlsx_path=xlsx_path,
        orientation=orientation,
        approvals=approvals,
    )

    # 2. تحويل ملف الـ Excel إلى PDF — يحاول Windows أولاً ثم Linux fallback
    pdf_generated = False

    # --- الطريقة الأولى: Windows فقط عبر Microsoft Excel COM ---
    if os.name == "nt":
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()

            excel_app = win32com.client.DispatchEx("Excel.Application")
            excel_app.Visible = False
            excel_app.DisplayAlerts = False

            wb = excel_app.Workbooks.Open(xlsx_path)
            # Type 0 = xlTypePDF
            wb.ExportAsFixedFormat(0, pdf_path)
            wb.Close(False)
            excel_app.Quit()
            pdf_generated = True
            print(f"[Windows] Excel -> PDF via COM success: {pdf_path}")
        except Exception as win_err:
            print(f"[Windows] win32com failed: {win_err}")

    # --- الطريقة الثانية: LibreOffice headless (Windows & Linux fallback) ---
    if not pdf_generated:
        try:
            libreoffice_cmd = "libreoffice"
            if os.name == "nt":
                lo_path_1 = r"C:\Program Files\LibreOffice\program\soffice.exe"
                lo_path_2 = r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
                if os.path.exists(lo_path_1):
                    libreoffice_cmd = lo_path_1
                elif os.path.exists(lo_path_2):
                    libreoffice_cmd = lo_path_2
                else:
                    libreoffice_cmd = "soffice"

            pdf_dir_lo = os.path.dirname(pdf_path)
            result = subprocess.run(
                [
                    libreoffice_cmd,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    pdf_dir_lo,
                    xlsx_path,
                ],
                timeout=60,
                capture_output=True,
                text=True,
            )

            generated_name = os.path.splitext(os.path.basename(xlsx_path))[0] + ".pdf"
            generated_path = os.path.join(pdf_dir_lo, generated_name)

            if os.path.exists(generated_path) and generated_path != pdf_path:
                os.rename(generated_path, pdf_path)

            if os.path.exists(pdf_path):
                pdf_generated = True
                print(f"[Fallback] Excel -> PDF via LibreOffice success: {pdf_path}")
            else:
                print(
                    f"[Fallback] LibreOffice ran but PDF not found. stdout: {result.stdout} stderr: {result.stderr}"
                )
        except FileNotFoundError:
            print(
                "[Fallback] LibreOffice not found. Windows: Install LibreOffice. Linux: sudo apt install libreoffice"
            )
        except Exception as lo_err:
            print(f"[Fallback] LibreOffice error: {lo_err}")

    if pdf_generated and os.path.exists(pdf_path):
        try:
            from extensions import db
            from models import EmailReceiver, GameReport

            GameReport.query.filter_by(session_id=session_id).update(
                {"pdf_file_path": pdf_path}
            )
            db.session.commit()
            print(f"[DB] Saved pdf_file_path '{pdf_path}' for session {session_id}")

            # --- Check if this is an initial generation or an approval regeneration ---
            from models import ReportApproval
            has_approvals = ReportApproval.query.filter_by(session_id=session_id).first() is not None
            
            # --- Email Integration (Attachment) ---
            if not has_approvals:
                from utils_mail import send_notification_emails

                receivers = [
                    r.email for r in EmailReceiver.query.filter_by(is_active=True).all()
                ]
                if receivers:
                    print(
                        f"Sending emails with PDF attachment to {len(receivers)} receivers..."
                    )
                    success = send_notification_emails(
                        pdf_path, area_name, date_str, receivers
                    )
                    if success:
                        print("Emails sent successfully!")
                    else:
                        print("Failed to send emails.")
                else:
                    print("No active email receivers found. Skipping email.")
            else:
                print("Report already has approvals. Skipping duplicate email notification.")

            # --- Google Drive Integration ---
            from models import log_system_event
            from utils_drive import upload_pdf_to_drive

            year_str = date_str.split("-")[0]
            month_str = date_str.split("-")[1]
            print("Uploading to Google Drive...")
            upload_success = upload_pdf_to_drive(
                pdf_path, year_str, month_str, area_name
            )

            if upload_success:
                log_system_event(
                    "System",
                    "Drive Upload Success",
                    details=f"Uploaded {os.path.basename(pdf_path)}",
                    level="INFO",
                )
                db.session.commit()
            else:
                log_system_event(
                    "System",
                    "Drive Upload Ignored/Failed",
                    details=f"Check logs or credentials.",
                    level="WARNING",
                )
                db.session.commit()

        except Exception as db_err:
            print(f"[Error in post-PDF process]: {db_err}")

    # تنظيف المجلد المؤقت بالكامل (يشمل الـ xlsx وأي ملفات مؤقتة أخرى)
    shutil.rmtree(temp_dir, ignore_errors=True)

    return None, pdf_path


def json_loads(data):
    try:
        return json.loads(data)
    except Exception:
        return {}


if __name__ == "__main__":
    import sys

    from app import app

    if len(sys.argv) > 1:
        session_id_arg = sys.argv[1]
        with app.app_context():
            generate_report_excel_and_pdf(session_id_arg)
