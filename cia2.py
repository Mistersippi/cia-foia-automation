from flask import Flask, render_template, request, jsonify, send_file
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import requests
import time
import logging
import os
from datetime import datetime, timedelta
import io
import zipfile
from pyairtable import Table
from pdfminer.high_level import extract_text  # Placeholder for PDF extraction
import docx  # Placeholder for DOCX extraction
import openai  # For ChatGPT API
from git import Repo  # Optional: for Git integration
import subprocess  # For calling FFmpeg (if needed for future features)
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------------------
# SET YOUR API KEYS / CONFIG HERE
# ---------------------------
openai.api_key = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "YOUR_AIRTABLE_API_KEY_HERE")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "YOUR_AIRTABLE_BASE_ID_HERE")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Documents")
AIRTABLE_IMAGE_PROMPTS_TABLE = os.getenv("AIRTABLE_IMAGE_PROMPTS_TABLE", "ImagePrompts")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "YOUR_ELEVENLABS_API_KEY_HERE")
# ---------------------------

logging.basicConfig(level=logging.INFO)
BASE_URL = "https://www.cia.gov"

app = Flask(__name__)

# ---------------------------
# AIRTABLE DATABASE FUNCTIONS
# ---------------------------
documents_table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
image_prompts_table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_IMAGE_PROMPTS_TABLE)

def store_document(title, url, report, summary, video_script, video_file):
    data = {
        "title": title,
        "url": url,
        "report": report,
        "summary": summary,
        "video_script": video_script,
        "video_file": video_file,
        "processed_at": datetime.now().isoformat()
    }
    records = documents_table.all(formula=f"{{url}} = '{url}'")
    if not records:
        documents_table.create(data)

def store_image_prompts(document_url, prompts):
    for i, prompt in enumerate(prompts, start=1):
        data = {
            "document_url": document_url,
            "prompt_index": i,
            "prompt": prompt,
            "image_url": ""
        }
        image_prompts_table.create(data)

def search_documents(keyword, start_date, end_date):
    formula_parts = []
    if keyword:
        keyword_escaped = keyword.replace("'", "\\'")
        formula_parts.append(f"FIND('{keyword_escaped}', {{title}})")
        formula_parts.append(f"FIND('{keyword_escaped}', {{report}})")
        formula_parts.append(f"FIND('{keyword_escaped}', {{summary}})")
        search_formula = "OR(" + ", ".join(formula_parts) + ")"
    else:
        search_formula = ""
    date_formula = ""
    if start_date:
        date_formula = f"IS_AFTER({{processed_at}}, '{start_date}')"
    if end_date:
        if date_formula:
            date_formula = f"AND({date_formula}, IS_BEFORE({{processed_at}}, '{end_date}'))"
        else:
            date_formula = f"IS_BEFORE({{processed_at}}, '{end_date}')"
    if search_formula and date_formula:
        formula = f"AND({search_formula}, {date_formula})"
    elif search_formula:
        formula = search_formula
    elif date_formula:
        formula = date_formula
    else:
        formula = ""
    return documents_table.all(formula=formula) if formula else documents_table.all()

# ---------------------------
# SCRAPING FUNCTIONS
# ---------------------------
def build_cia_search_url(keyword, start_date, end_date):
    start_str = f"{start_date}T00%3A00%3A00Z" if start_date else "1900-01-01T00%3A00%3A00Z"
    end_str = f"{end_date}T00%3A00%3A00Z" if end_date else "2100-01-01T00%3A00%3A00Z"
    date_filter = f"f%5B0%5D=ds_created%3A%5B{start_str}%20TO%20{end_str}%5D"
    keyword_path = f"/readingroom/search/site/{keyword}" if keyword else "/readingroom/search/site"
    full_url = f"{BASE_URL}{keyword_path}?{date_filter}"
    return full_url

def fetch_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return BeautifulSoup(response.text, "html.parser")
        else:
            logging.error(f"Failed to fetch {url}: {response.status_code}")
    except Exception as e:
        logging.error(f"Error fetching {url}: {str(e)}")
    return None

def extract_document_list(soup):
    docs = []
    if not soup:
        return docs
    results = soup.find("ol", class_="search-results")
    if results:
        for li in results.find_all("li"):
            title_tag = li.find("h3", class_="title")
            if title_tag:
                a_tag = title_tag.find("a")
                if a_tag and a_tag.get("href"):
                    title = title_tag.get_text(strip=True)
                    doc_url = BASE_URL + a_tag.get("href")
                    docs.append({"title": title, "url": doc_url})
    return docs

def get_next_page_url(soup):
    if not soup:
        return None
    pager = soup.find("ul", class_="pager")
    if pager:
        next_li = pager.find("li", class_="pager-next")
        if next_li and next_li.find("a"):
            return BASE_URL + next_li.find("a").get("href")
    return None

# ---------------------------
# DOCUMENT PROCESSING FUNCTIONS
# ---------------------------
def download_file(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
        else:
            logging.error(f"Failed to download file from {url}")
    except Exception as e:
        logging.error(f"Error downloading file from {url}: {str(e)}")
    return None

def extract_text_from_file(file_content, file_url):
    if file_url.lower().endswith('.pdf'):
        return "Extracted text from PDF (placeholder)."
    elif file_url.lower().endswith('.docx'):
        return "Extracted text from DOCX (placeholder)."
    return ""

def call_chatgpt_report(text):
    prompt = f"Generate a detailed report based on the following text:\n\n{text}"
    return "Detailed report (placeholder)."

def call_chatgpt_summary(report):
    prompt = f"Provide a bullet-point summary for the following detailed report:\n\n{report}"
    return "Bullet-point summary (placeholder)."

def call_video_script(report):
    prompt = f"Convert the following detailed report into a 5-minute voiceover/video script:\n\n{report}"
    return "Video script (placeholder)."

# ---------------------------
# IMAGE PROMPT GENERATION FUNCTIONS
# ---------------------------
def generate_image_prompts(video_script, num_prompts=60):
    segments = [s.strip() for s in video_script.split('.') if s.strip()]
    if len(segments) < num_prompts:
        segments += [segments[-1]] * (num_prompts - len(segments))
    else:
        segments = segments[:num_prompts]
    prompts = [f"Generate an image that illustrates: {seg}" for seg in segments]
    return prompts

# Note: `store_image_prompts` is already defined under AIRTABLE DATABASE FUNCTIONS

# ---------------------------
# FULL DOCUMENT PROCESSING PIPELINE
# ---------------------------
def process_document(doc_title, doc_url):
    logging.info(f"Processing document: {doc_url}")
    soup = fetch_page(doc_url)
    if not soup:
        return None
    download_link = soup.find("a", text=lambda t: t and "Download" in t)
    if download_link:
        file_url = BASE_URL + download_link.get("href")
        file_content = download_file(file_url)
        if file_content:
            text = extract_text_from_file(file_content, file_url)
            report = call_chatgpt_report(text)
            summary = call_chatgpt_summary(report)
            video_script = call_video_script(report)
            prompts = generate_image_prompts(video_script, num_prompts=60)
            store_image_prompts(doc_url, prompts)
            store_document(doc_title, doc_url, report, summary, video_script, "Prompts Generated")
            return {"report": report, "summary": summary, "video_script": video_script, "video_file": "Prompts Generated"}
    logging.error("Download link not found or file download failed.")
    return None

def scrape_and_store_all(start_url):
    current_url = start_url
    while current_url:
        soup = fetch_page(current_url)
        docs = extract_document_list(soup)
        for d in docs:
            process_document(d["title"], d["url"])
            time.sleep(1)
        current_url = get_next_page_url(soup)

def daily_update():
    logging.info("Running daily update...")
    url = build_cia_search_url(keyword="", start_date="2025-01-01", end_date="2026-01-01")
    scrape_and_store_all(url)

# ---------------------------
# FLASK ROUTES
# ---------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/search_cia", methods=["GET", "POST"])
def search_cia():
    if request.method == "POST":
        keyword = request.form.get("keyword", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        search_url = build_cia_search_url(keyword, start_date, end_date)
        results = []
        current_url = search_url
        while current_url:
            soup = fetch_page(current_url)
            docs = extract_document_list(soup)
            for d in docs:
                proc_result = process_document(d["title"], d["url"])
                if proc_result:
                    results.append({
                        "title": d["title"],
                        "url": d["url"],
                        "report": proc_result["report"],
                        "summary": proc_result["summary"],
                        "video_script": proc_result["video_script"],
                        "video_file": proc_result["video_file"]
                    })
                else:
                    results.append({
                        "title": d["title"],
                        "url": d["url"],
                        "report": "Already in Airtable or no link found",
                        "summary": "",
                        "video_script": "",
                        "video_file": ""
                    })
                time.sleep(1)
            current_url = get_next_page_url(soup)
        return render_template("search_cia.html", results=results, keyword=keyword, start_date=start_date, end_date=end_date)
    return render_template("search_cia.html", results=None, keyword="", start_date="", end_date="")

@app.route("/process_document", methods=["POST"])
def process_document_route():
    doc_url = request.form.get("doc_url")
    doc_title = request.form.get("doc_title", doc_url)
    if not doc_url:
        return jsonify({"error": "No document URL provided."}), 400
    result = process_document(doc_title, doc_url)
    if result:
        return jsonify(result)
    return jsonify({"error": "Processing failed."}), 500

@app.route("/download_images")
def download_images():
    doc_url = request.args.get("doc_url")
    if not doc_url:
        return "Missing document URL", 400
    records = image_prompts_table.all(formula=f"AND({{document_url}} = '{doc_url}', LEN({{image_url}}) > 0)")
    if not records:
        return "No images available for this document", 404
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for record in records:
            image_url = record["fields"].get("image_url")
            if image_url:
                img_data = requests.get(image_url).content
                filename = f"prompt_{record['fields'].get('prompt_index')}.png"
                zip_file.writestr(filename, img_data)
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", download_name="images.zip", as_attachment=True)

# ---------------------------
# MAIN EXECUTION
# ---------------------------
if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_update, 'interval', days=1, next_run_time=datetime.now() + timedelta(seconds=10))
    scheduler.start()
    app.run(debug=True)

