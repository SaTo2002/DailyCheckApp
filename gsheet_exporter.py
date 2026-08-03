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

# Mapping of Game Names to their TEXT COMMENTS section cell in the Google Sheet (Column B)
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

# Mapping of Game Names to their LEFT-SIDE MAP IMAGE section cell in the Google Sheet (Column B)
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

def export_report_to_pdf(report_session_id, monitor_name, area_name, checks_dict, game_notes_dict, game_maps_dict, date_str, output_pdf_path):
    """
    Fills Google Sheet Template directly, exports PDF, and cleans up populated values.
    Does not clone files, preventing Google Drive service account storage quota limits.
    """
    # 1. Auth Google APIs
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)
    gc = gspread.authorize(creds)
    
    # 2. Open Original Shared Spreadsheet directly
    sh = gc.open_by_key(TEMPLATE_SPREADSHEET_ID)
    ws = sh.sheet1
    
    # Track updated cells for cleanup
    cleared_ranges = ['B5', 'H5']
    
    try:
        # 3. Fill Header details (Inspector Name in B5 & Date in H5)
        ws.update_acell('B5', f"Name: {monitor_name}")
        ws.update_acell('H5', date_str)
        
        # 4. Read questions rows and set check mark symbols (✔) in OK / NOK columns
        all_rows = ws.get_all_values()
        
        # Normalize keys in checks_dict for flexible whitespace matching
        normalized_checks = {' '.join(k.split()).lower(): v for k, v in checks_dict.items()}

        updates = []
        for r_idx, row in enumerate(all_rows, start=1):
            if len(row) > 1:
                q_text = ' '.join(row[1].split()).lower() # Normalize newlines and extra spaces
                if q_text in normalized_checks:
                    status = normalized_checks[q_text]
                    if status == 'OK':
                        updates.append({'range': f'G{r_idx}', 'values': [['✔']]})
                        cleared_ranges.append(f'G{r_idx}')
                    elif status == 'NOK':
                        updates.append({'range': f'H{r_idx}', 'values': [['✔']]})
                        cleared_ranges.append(f'H{r_idx}')
        
        # 5. Fill Game Description Notes into right-side Comments sections
        cell_notes_map = {}
        for game_name, note_text in game_notes_dict.items():
            if note_text and note_text.strip():
                target_cell = None
                # Check for exact key match first
                for mapped_game, cell_addr in GAME_COMMENT_CELLS.items():
                    if mapped_game.lower() == game_name.lower():
                        target_cell = cell_addr
                        break
                # Fallback substring match
                if not target_cell:
                    for mapped_game, cell_addr in GAME_COMMENT_CELLS.items():
                        if mapped_game.lower() in game_name.lower() or game_name.lower() in mapped_game.lower():
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
                    for mapped_game, cell_addr in GAME_MAP_IMAGE_CELLS.items():
                        if mapped_game.lower() in game_name.lower() or game_name.lower() in mapped_game.lower():
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
                'B91': 'Free Jump',
                'B101': 'Airtrack',
                'B112': 'Airbag, Dodgeball & Performance',
                'B133': 'Entrance Of Dodge',
                'B142': 'Ninja Course',
                'B153': 'Laser Room',
                'B164': 'Matrix',
                'B175': 'Preparation Area',
                'B186': 'Lounge',
                'B197': 'F.O'
            }
            cleanup_updates = []
            for r in set(cleared_ranges):
                if r == 'B5':
                    cleanup_updates.append({'range': 'B5', 'values': [['Name:']]})
                elif r in title_restorations:
                    cleanup_updates.append({'range': r, 'values': [[title_restorations[r]]]})
                else:
                    cleanup_updates.append({'range': r, 'values': [['']]})
            if cleanup_updates:
                ws.batch_update(cleanup_updates)
        except Exception:
            pass

print("Helper function logic created successfully!")
