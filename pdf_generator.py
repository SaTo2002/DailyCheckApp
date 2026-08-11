import os
import openpyxl

def generate_report_excel_and_pdf(session_id):
    """
    يقوم بتصدير تقرير الـ Excel من القوالب المحلية الرسمية في Exsl/،
    ثم يحوله فوراً إلى ملف PDF رسمي بنفس الشكل في مجلد pdfs/YYYY/MM/.
    يرجع مسار ملف الـ XLSX ومسار ملف الـ PDF.
    """
    from models import GameReport, GameModel
    
    reports = GameReport.query.filter_by(session_id=session_id).all()
    if not reports:
        return None, None

    area_name = reports[0].area_id
    monitor_name = reports[0].monitor_name
    ts = reports[0].timestamp
    date_str = ts.strftime('%Y-%m-%d')
    
    game_checks = {}
    game_notes = {}
    game_maps = {}
    
    for r in reports:
        game_model = GameModel.query.filter((GameModel.id == r.game_id) | (GameModel.name == r.game_id)).first()
        game_name = game_model.name if game_model else r.game_id
        
        actual_check_names = [c['name'] for c in json_loads(game_model.checks)] if game_model and game_model.checks else []
        checks_dict = {}
        for k, v in (json_loads(r.checks_data) if r.checks_data else {}).items():
            if k.startswith('check_'):
                try: 
                    q_title = actual_check_names[int(k.split('_')[1]) - 1] if int(k.split('_')[1]) - 1 < len(actual_check_names) else k
                    checks_dict[q_title] = 'OK' if (v == 'سليم' or v == 'OK') else 'NOK'
                except Exception: 
                    checks_dict[k] = v
            else: 
                checks_dict[k] = v
                
        game_checks[game_name] = checks_dict
                
        if r.notes and r.notes.strip():
            game_notes[game_name] = r.notes.strip()
            
        if r.map_image_path:
            game_maps[game_name] = r.map_image_path

    year_folder = ts.strftime('%Y')
    month_folder = ts.strftime('%m')
    ddmmyy_date = ts.strftime('%d%m%y')
    
    # كود الفرع: يُقرأ من ملف .env — يتغير فقط لو فتحنا فرع جديد
    branch_code = os.getenv('BRANCH_CODE', 'alm').lower().strip()
        
    # تنظيف اسم المنطقة لاستخدامه كمجلد مستقل (مثل: Park, Kids, Kickerz, Bowling)
    area_folder_name = "".join([c if c.isalnum() or c in (' ', '_', '-') else '' for c in area_name]).strip()
    if not area_folder_name:
        area_folder_name = "General"

    # مجلد الـ PDF الدائم فقط: (pdfs / السنة / الشهر / اسم_المنطقة)
    pdf_dir = os.path.join('pdfs', year_folder, month_folder, area_folder_name)
    os.makedirs(pdf_dir, exist_ok=True)

    file_basename = f"{ddmmyy_date}_{branch_code}_{session_id[:6]}"
    pdf_path = os.path.abspath(os.path.join(pdf_dir, f"{file_basename}.pdf"))

    # مجلد مؤقت للـ xlsx فقط — يُمسح تلقائياً بعد التحويل (لا يُحفظ على الديسك نهائياً)
    import tempfile
    temp_dir = tempfile.mkdtemp()
    xlsx_path = os.path.abspath(os.path.join(temp_dir, f"{file_basename}.xlsx"))


    # قراءة اتجاه طباعة المنطقة المحدد من قاعدة البيانات
    from models import Area
    area_obj = Area.query.filter((Area.name == area_name) | (Area.name.like(f"%{area_name}%"))).first()
    orientation = area_obj.pdf_orientation if area_obj and area_obj.pdf_orientation else 'portrait'

    # 1. تصدير ملف الـ Excel المحلي
    from excel_exporter import export_report_to_excel
    export_report_to_excel(
        report_session_id=session_id,
        monitor_name=monitor_name,
        area_name=area_name,
        checks_dict=game_checks,
        game_notes_dict=game_notes,
        game_maps_dict=game_maps,
        date_str=date_str,
        output_xlsx_path=xlsx_path,
        orientation=orientation
    )

    # 2. تحويل ملف الـ Excel إلى PDF — يحاول Windows أولاً ثم Linux fallback
    pdf_generated = False

    # --- الطريقة الأولى: Windows فقط عبر Microsoft Excel COM ---
    if os.name == 'nt':
        try:
            import win32com.client
            import pythoncom
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
            print(f"✅ [Windows] Excel → PDF via COM: {pdf_path}")
        except Exception as win_err:
            print(f"⚠️ [Windows] win32com failed: {win_err}")

    # --- الطريقة الثانية: Linux / Mac عبر LibreOffice headless ---
    if not pdf_generated:
        try:
            import subprocess
            pdf_dir = os.path.dirname(pdf_path)
            result = subprocess.run(
                [
                    'libreoffice', '--headless', '--convert-to', 'pdf',
                    '--outdir', pdf_dir, xlsx_path
                ],
                timeout=60,
                capture_output=True,
                text=True
            )
            # LibreOffice saves as <filename>.pdf in the same outdir
            generated_name = os.path.splitext(os.path.basename(xlsx_path))[0] + '.pdf'
            generated_path = os.path.join(pdf_dir, generated_name)

            # Rename to match expected pdf_path if different
            if os.path.exists(generated_path) and generated_path != pdf_path:
                os.rename(generated_path, pdf_path)

            if os.path.exists(pdf_path):
                pdf_generated = True
                print(f"✅ [Linux] Excel → PDF via LibreOffice: {pdf_path}")
            else:
                print(f"⚠️ [Linux] LibreOffice ran but PDF not found. stdout: {result.stdout} stderr: {result.stderr}")
        except FileNotFoundError:
            print("⚠️ [Linux] LibreOffice not installed. Install it with: sudo apt install libreoffice")
        except Exception as lo_err:
            print(f"⚠️ [Linux] LibreOffice conversion failed: {lo_err}")

    if not pdf_generated:
        print("❌ PDF generation failed on both Windows (COM) and Linux (LibreOffice).")

    # تنظيف المجلد المؤقت بالكامل (يشمل الـ xlsx وأي ملفات مؤقتة أخرى)
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Error removing temp directory: {e}")


    return None, pdf_path

def json_loads(data):
    import json
    try:
        return json.loads(data)
    except Exception:
        return {}
