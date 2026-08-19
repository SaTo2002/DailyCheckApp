import os
import re
import glob

# Pattern to find opening form tags that do NOT already have the csrf token immediately after
# We'll just replace all <form ...> with <form ...>\n<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
# Then we'll clean up any double csrf tokens just in case

templates_dir = r"e:\DailyCheckApp\templates"
html_files = glob.glob(os.path.join(templates_dir, "**/*.html"), recursive=True)

csrf_input = '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>'

for file_path in html_files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # If already has csrf_token, skip to avoid duplicates if run multiple times
    if 'name="csrf_token"' in content:
        print(f"Skipping {file_path} (already has CSRF)")
        continue

    # Regex to find <form ...> or <form>
    # Note: re.IGNORECASE handles <FORM> just in case, though they are usually lowercase
    new_content = re.sub(r'(<form[^>]*>)', r'\1' + csrf_input, content, flags=re.IGNORECASE)

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {file_path}")

print("Done inserting CSRF tokens.")
