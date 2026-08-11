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
    
    branch_clean = area_name.lower().strip()
    if 'almaza' in branch_clean or 'park' in branch_clean:
        branch_code = 'alm'
    else:
        branch_code = branch_clean[:3] if len(branch_clean) >= 3 else branch_clean
        
    # تنظيف اسم المنطقة لاستخدامه كمجلد مستقل (مثل: Park, Kids, Kickerz, Bowling)
    area_folder_name = "".join([c if c.isalnum() or c in (' ', '_', '-') else '' for c in area_name]).strip()
    if not area_folder_name:
        area_folder_name = "General"

    # مجلدات الحفظ بالترتيب المفضل: (نوع_التقرير / السنة / الشهر / اسم_المنطقة)
    excel_dir = os.path.join('reports_excel', year_folder, month_folder, area_folder_name)
    pdf_dir = os.path.join('pdfs', year_folder, month_folder, area_folder_name)
    os.makedirs(excel_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)
    
    file_basename = f"{ddmmyy_date}_{branch_code}_{session_id[:6]}"
    xlsx_path = os.path.abspath(os.path.join(excel_dir, f"{file_basename}.xlsx"))
    pdf_path = os.path.abspath(os.path.join(pdf_dir, f"{file_basename}.pdf"))

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

    # 2. تحويل ملف الـ Excel المحفوظ تلقائياً إلى PDF عبر pywin32 COM
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
        print(f"✅ Excel to PDF conversion successful: {pdf_path}")
    except Exception as pdf_err:
        print(f"⚠️ Warning: Could not convert Excel to PDF via COM: {pdf_err}")
    finally:
        # Clean up temporary Excel file from disk immediately (Keep PDFs only)
        if os.path.exists(xlsx_path):
            try:
                os.remove(xlsx_path)
            except Exception as e:
                print(f"Error removing temp excel file: {e}")

    return None, pdf_path

def json_loads(data):
    import json
    try:
        return json.loads(data)
    except Exception:
        return {}
