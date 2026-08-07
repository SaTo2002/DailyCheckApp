import os
import openpyxl
from openpyxl.drawing.image import Image as OpenPyxlImage
from PIL import Image as PILImage

# Exact template paths for each area/branch
EXCEL_TEMPLATES = {
    'park': os.path.join(os.path.dirname(__file__), 'Exsl', 'DailyCheck_Park.xlsx'),
    'kids': os.path.join(os.path.dirname(__file__), 'Exsl', 'DailyCheck_Kids.xlsx'),
    'kickerz': os.path.join(os.path.dirname(__file__), 'Exsl', 'DailyCheck_Kickerz.xlsx'),
    'bowling': os.path.join(os.path.dirname(__file__), 'Exsl', 'DailyCheck_Bowling.xlsx')
}

GAME_COMMENT_CELLS = {
    'Free Jump': 'G92',
    'Airtrack': 'B102',
    'Performance(map)': 'G113',
    'Dodgeball(map)': 'G122',
    'Airbag(map)': 'G133',
    'Ninja Course': 'B143',
    'Laser Room': 'B154',
    'Matrix': 'G165',
    'Preparation Area': 'B176',
    'Lounge': 'B187',
    'F.O': 'B198',
    'Health & Safety': 'B84'
}

GAME_MAP_IMAGE_CELLS = {
    'Free Jump': 'B92',
    'Airbag, Dodgeball & Performance': 'B113',
    'Airbag,Dodgeball & Performance(OK or NOK)': 'B113',
    'Performance(map)': 'B113',
    'Performance': 'B113',
    'Dodgeball(map)': 'B122',
    'Dodgeball': 'B122',
    'Entrance Of Dodge': 'B134',
    'Airbag(map)': 'B134',
    'Airbag': 'B134',
    'Matrix(map)': 'B165',
    'Matrix': 'B165',
    'MATRIX': 'B165'
}

def export_report_to_excel(report_session_id, monitor_name, area_name, checks_dict, game_notes_dict, game_maps_dict, date_str, output_xlsx_path, orientation='portrait'):
    """
    Fills local Excel template file directly using openpyxl, populates values and issue map images,
    and saves to output_xlsx_path. Completely replaces Google Sheets dependency.
    """
    # Select template based on area_name
    area_clean = area_name.lower().strip()
    template_path = EXCEL_TEMPLATES.get('park')
    for key, path in EXCEL_TEMPLATES.items():
        if key in area_clean:
            template_path = path
            break
            
    if not os.path.exists(template_path):
        # Fallback to Park template
        template_path = EXCEL_TEMPLATES['park']
        
    wb = openpyxl.load_workbook(template_path)
    ws = wb.active

    # 1. Fill Header (B5: Name, H5: Date)
    ws['B5'] = f"Name: {monitor_name}"
    ws['H5'] = f"Date: {date_str}"

    # 2. Map questions rows per Section in Column B
    # Each section (e.g. F.O, Lounge, Airtrack...) maps its own question text -> row number
    section_map = {}
    current_sec = "General"
    section_map[current_sec] = {}
    section_title_rows = set()
    
    for r in range(6, 90):
        col_g = str(ws.cell(row=r, column=7).value or '').strip()
        col_h = str(ws.cell(row=r, column=8).value or '').strip()
        cell_val = ws.cell(row=r, column=2).value
        
        if col_g == 'OK' and col_h == 'NOK':
            section_title_rows.add(r)
            current_sec = ' '.join(str(cell_val).strip().split()).lower()
            section_map[current_sec] = {}
        elif cell_val:
            clean_txt = ' '.join(str(cell_val).strip().split()).lower()
            section_map[current_sec][clean_txt] = r

    # 3. Fill Checkmarks (Col G: OK, Col H: NOK) per exact section
    for game_name, game_checks in checks_dict.items():
        gn_clean = ' '.join(game_name.strip().split()).lower()
        
        # Match game to Excel section
        matched_sec_dict = None
        for sec_name, q_row_dict in section_map.items():
            if sec_name in gn_clean or gn_clean in sec_name:
                matched_sec_dict = q_row_dict
                break
                
        # If no section match, fallback to global lookup
        if not matched_sec_dict:
            global_qs = {}
            for qd in section_map.values():
                global_qs.update(qd)
            matched_sec_dict = global_qs
            
        for q_name, status in game_checks.items():
            clean_q = ' '.join(q_name.strip().split()).lower()
            if clean_q in matched_sec_dict:
                r_idx = matched_sec_dict[clean_q]
                if r_idx not in section_title_rows:
                    if status == 'OK':
                        ws.cell(row=r_idx, column=7, value='✔')
                    elif status == 'NOK':
                        ws.cell(row=r_idx, column=8, value='✔')

    # 4. Fill Comments
    cell_notes_map = {}
    for game_name, note_text in game_notes_dict.items():
        if note_text and note_text.strip():
            target_cell = None
            gn_clean = ' '.join(game_name.strip().split()).lower()
            for mapped_game, cell_addr in GAME_COMMENT_CELLS.items():
                mg_clean = ' '.join(mapped_game.strip().split()).lower()
                if mg_clean == gn_clean:
                    target_cell = cell_addr
                    break
            if not target_cell:
                for mapped_game, cell_addr in GAME_COMMENT_CELLS.items():
                    mg_clean = ' '.join(mapped_game.strip().split()).lower()
                    if mg_clean in gn_clean or gn_clean in mg_clean:
                        target_cell = cell_addr
                        break
            if target_cell:
                if target_cell not in cell_notes_map:
                    cell_notes_map[target_cell] = []
                cell_notes_map[target_cell].append(note_text.strip())

    from openpyxl.styles import Alignment, Font
    for cell_addr, notes_list in cell_notes_map.items():
        cell = ws[cell_addr]
        
        # Bullet-Point Demarcation Flow: Clearly separate distinct notes with bold bullet points (•)
        all_paragraphs = []
        for n in notes_list:
            if not n: continue
            lines = [line.strip() for line in n.splitlines() if line.strip()]
            if lines:
                # Add a bullet point to clearly separate each distinct item/issue
                paragraph = " • " + "   • ".join(lines)
                all_paragraphs.append(paragraph)
                    
        cell.value = "   ".join(all_paragraphs)
        
        # Word-like Rich Text Alignment & Styling (RTL Arabic, Wrap Text, Top Alignment, Clean Font)
        cell.alignment = Alignment(wrap_text=True, vertical='top', horizontal='right', readingOrder=2)
        cell.font = Font(name='Arial', size=10, bold=False)

    # 5. Insert Map Images directly inside cells (In-Cell Anchoring)
    if game_maps_dict:
        for game_name, map_info in game_maps_dict.items():
            drawing_path = map_info.get('drawing', '') if isinstance(map_info, dict) else map_info
            base_path = map_info.get('base', '') if isinstance(map_info, dict) else ''
            
            if drawing_path:
                d_path = drawing_path.lstrip('/')
                b_path = base_path.lstrip('/') if base_path else ''
                
                if not os.path.isabs(d_path): d_path = os.path.abspath(d_path)
                if b_path and not os.path.isabs(b_path): b_path = os.path.abspath(b_path)

                if os.path.exists(d_path):
                    target_cell = None
                    gn_clean = game_name.lower().replace('(map)', '').strip()
                    for mapped_game, cell_addr in GAME_MAP_IMAGE_CELLS.items():
                        mg_clean = mapped_game.lower().replace('(map)', '').strip()
                        if mg_clean == gn_clean:
                            target_cell = cell_addr
                            break
                    if not target_cell:
                        for mapped_game, cell_addr in GAME_MAP_IMAGE_CELLS.items():
                            mg_clean = mapped_game.lower().replace('(map)', '').strip()
                            if mg_clean in gn_clean or gn_clean in mg_clean:
                                target_cell = cell_addr
                                break
                    if target_cell:
                        try:
                            # 1. Overlay Drawing onto Base Map if present
                            if b_path and os.path.exists(b_path):
                                base_img = PILImage.open(b_path).convert("RGBA")
                                draw_img = PILImage.open(d_path).convert("RGBA")
                                draw_resized = draw_img.resize(base_img.size, PILImage.Resampling.LANCZOS)
                                final_img = PILImage.alpha_composite(base_img, draw_resized)
                                
                                temp_dir = os.path.join("static", "uploads", "temp_composites")
                                os.makedirs(temp_dir, exist_ok=True)
                                img_to_insert = os.path.abspath(os.path.join(temp_dir, f"excel_{os.path.basename(d_path)}"))
                                final_img.save(img_to_insert, "PNG")
                            else:
                                img_to_insert = d_path

                            # Find merged range for target cell to compute exact cell box dimensions
                            target_range = None
                            for rng in ws.merged_cells.ranges:
                                if rng.start_cell.coordinate == target_cell:
                                    target_range = rng
                                    break
                                    
                            # 1. Determine exact merged cell box dimensions dynamically for any box
                            cell_w_px = 500
                            cell_h_px = 200
                            if target_range:
                                col_letters = [openpyxl.utils.get_column_letter(c) for c in range(target_range.min_col, target_range.max_col + 1)]
                                total_w = sum((ws.column_dimensions[c].width or 13.0) for c in col_letters)
                                total_h = sum((ws.row_dimensions[r].height or 16.5) for r in range(target_range.min_row, target_range.max_row + 1))
                                cell_w_px = int(total_w * 7.5 + len(col_letters) * 4)
                                cell_h_px = int(total_h * 1.333)
                                
                            # 2. Resize image dynamically leaving 12px margin padding (Preserves black cell borders 100%)
                            avail_w = max(50, cell_w_px - 30)
                            avail_h = max(30, cell_h_px - 24)  # Leave 12px padding top and bottom so borders remain clear
                            
                            pil_img = PILImage.open(img_to_insert)
                            pil_img.thumbnail((avail_w, avail_h), PILImage.Resampling.LANCZOS)
                            
                            temp_fit_dir = os.path.join("static", "uploads", "temp_composites")
                            os.makedirs(temp_fit_dir, exist_ok=True)
                            fit_path = os.path.abspath(os.path.join(temp_fit_dir, f"centered_{os.path.basename(d_path)}"))
                            pil_img.save(fit_path, "PNG")

                            # 3. Calculate horizontal and vertical offset to center image with clean margins around borders
                            img_w, img_h = pil_img.size
                            offset_x_px = max(0, (cell_w_px - img_w) // 2)
                            offset_y_px = max(0, (cell_h_px - img_h) // 2)

                            # 1 Pixel = 9525 EMUs (English Metric Units) in openpyxl
                            from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
                            from openpyxl.drawing.xdr import XDRPositiveSize2D
                            
                            col_idx = (target_range.min_col - 1) if target_range else 1
                            row_idx = (target_range.min_row - 1) if target_range else 91
                            
                            marker = AnchorMarker(
                                col=col_idx,
                                colOff=int(offset_x_px * 9525),
                                row=row_idx,
                                rowOff=int(offset_y_px * 9525)
                            )
                            size = XDRPositiveSize2D(int(img_w * 9525), int(img_h * 9525))
                            
                            img = OpenPyxlImage(fit_path)
                            img.anchor = OneCellAnchor(_from=marker, ext=size)
                            ws.add_image(img)
                        except Exception as img_err:
                            print(f"Error adding image to Excel: {img_err}")

    # Set Page Setup Properties: Dynamic Orientation & Fit All Columns on One Page
    if str(orientation).lower() == 'landscape':
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    else:
        ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
        
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    # Ensure target output directory exists
    os.makedirs(os.path.dirname(output_xlsx_path), exist_ok=True)
    wb.save(output_xlsx_path)
    return output_xlsx_path
