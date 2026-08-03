import os
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SERVICE_ACCOUNT_FILE = 'DailyGoogleApi.json'
TEMPLATE_SPREADSHEET_ID = '1HcnjSVFB5lP0B1hWgQanqxQ3WTsmg5brUuZCdL9M5rs'

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Mapping of Game Names to their TEXT COMMENTS section cell in the Google Sheet (Column A or F)
GAME_COMMENT_CELLS = {
    'Free Jump': 'F89',
    'Airtrack': 'A99',
    'Performance(map)': 'F110',
    'Dodgeball(map)': 'F119',
    'Airbag(map)': 'F130',
    'Ninja Course': 'A140',
    'Laser Room': 'A151',
    'Matrix': 'F162',
    'Preparation Area': 'A173',
    'Lounge': 'A184',
    'F.O': 'A195',
    'Health & Safety': 'A81'
}

# Mapping of Game Names to their LEFT-SIDE MAP IMAGE section cell in the Google Sheet (Column A)
GAME_MAP_IMAGE_CELLS = {
    'Free Jump': 'A89',
    'Airbag, Dodgeball & Performance': 'A110',
    'Airbag,Dodgeball & Performance(OK or NOK)': 'A110',
    'Performance(map)': 'A110',
    'Performance': 'A110',
    'Dodgeball(map)': 'A119',
    'Dodgeball': 'A119',
    'Entrance Of Dodge': 'A130',
    'Airbag(map)': 'A130',
    'Airbag': 'A130',
    'Matrix(map)': 'A161',
    'Matrix': 'A161',
    'MATRIX': 'A161'
}

def export_report_to_pdf(report_session_id, monitor_name, area_name, checks_dict, game_notes_dict, game_maps_dict, date_str, output_pdf_path):
    """
    Fills Google Sheet Template directly, exports PDF, and cleans up populated values.
    Does not clone files, preventing Google Drive service account storage quota limits.
    """
    # 1. Auth Google APIs
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)

    # Open Template Spreadsheet directly
    sh = gc.open_by_key(TEMPLATE_SPREADSHEET_ID)
    ws = sh.sheet1
    
    try:
        updates = []
        cleared_ranges = []

        # 2. Fill Name (A2) and Date (G2)
        updates.append({'range': 'A2', 'values': [[f"Name: {monitor_name}"]]})
        updates.append({'range': 'G2', 'values': [[date_str]]})
        cleared_ranges.extend(['A2', 'G2'])

        # 3. Read sheet structure once to map Question text to Rows (Row 3 to Row 86)
        sheet_rows = ws.get('A3:A86')
        question_to_row = {}
        for idx, row in enumerate(sheet_rows, start=3):
            if row and row[0].strip():
                clean_text = ' '.join(row[0].strip().split()).lower()
                question_to_row[clean_text] = idx

        # 4. Fill Checkmarks (✔) into OK (Col F) or NOK (Col G)
        for q_name, status in checks_dict.items():
            clean_q = ' '.join(q_name.strip().split()).lower()
            if clean_q in question_to_row:
                r_idx = question_to_row[clean_q]
                if status == 'OK':
                    updates.append({'range': f'F{r_idx}', 'values': [['✔']]})
                    cleared_ranges.append(f'F{r_idx}')
                elif status == 'NOK':
                    updates.append({'range': f'G{r_idx}', 'values': [['✔']]})
                    cleared_ranges.append(f'G{r_idx}')
        
        # 5. Fill Game Description Notes into right-side/full-width Comments sections
        cell_notes_map = {}
        for game_name, note_text in game_notes_dict.items():
            if note_text and note_text.strip():
                target_cell = None
                gn_clean = ' '.join(game_name.strip().split()).lower()
                # Check for exact key match first
                for mapped_game, cell_addr in GAME_COMMENT_CELLS.items():
                    mg_clean = ' '.join(mapped_game.strip().split()).lower()
                    if mg_clean == gn_clean:
                        target_cell = cell_addr
                        break
                # Fallback substring match
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

        for cell_addr, notes_list in cell_notes_map.items():
            combined_notes = "\n".join(notes_list)
            updates.append({'range': cell_addr, 'values': [[combined_notes]]})
            cleared_ranges.append(cell_addr)
        
        # 6. Insert Drawn Issue Maps into left-side Map Image Boxes
        if game_maps_dict:
            for game_name, map_img_url in game_maps_dict.items():
                if map_img_url:
                    gn_clean = ' '.join(game_name.strip().split()).lower()
                    for mapped_game, cell_addr in GAME_MAP_IMAGE_CELLS.items():
                        mg_clean = ' '.join(mapped_game.strip().split()).lower()
                        if mg_clean in gn_clean or gn_clean in mg_clean:
                            image_formula = f'=IMAGE("{map_img_url}")'
                            updates.append({'range': cell_addr, 'values': [[image_formula]]})
                            cleared_ranges.append(cell_addr)
                            break

        if updates:
            ws.batch_update(updates, value_input_option='USER_ENTERED')
            
        # 7. Export filled Google Sheet as PDF
        request = drive_service.files().export_media(
            fileId=TEMPLATE_SPREADSHEET_ID,
            mimeType='application/pdf'
        )
        with open(output_pdf_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                
    finally:
        # 8. Clean up template values to leave original sheet clean
        try:
            title_restorations = {
                'A88': 'Free Jump',
                'A98': 'Airtrack',
                'A109': 'Airbag, Dodgeball & Performance',
                'A130': 'Entrance Of Dodge',
                'A139': 'Ninja Course',
                'A150': 'Laser Room',
                'A161': 'Matrix',
                'A172': 'Preparation Area',
                'A183': 'Lounge',
                'A194': 'F.O'
            }
            cleanup_updates = []
            for r in set(cleared_ranges):
                if r == 'A2':
                    cleanup_updates.append({'range': 'A2', 'values': [['Name:']]})
                elif r in title_restorations:
                    cleanup_updates.append({'range': r, 'values': [[title_restorations[r]]]})
                else:
                    cleanup_updates.append({'range': r, 'values': [['']]})
            if cleanup_updates:
                ws.batch_update(cleanup_updates)
        except Exception:
            pass

print("Helper function logic created successfully!")
