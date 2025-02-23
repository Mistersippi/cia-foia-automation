from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import requests
import time
import logging
import os
from datetime import datetime, timedelta
from pyairtable import Table
from pdfminer.high_level import extract_text  # for PDF extraction (placeholder)
import docx  # for DOCX extraction (placeholder)
import openai  # for ChatGPT API
from git import Repo  # for Git integration (optional)
from moviepy.editor import ImageClip, concatenate_videoclips
from dotenv import load_dotenv
load_dotenv()

# ---------------------------
# SET YOUR API KEYS / CONFIG
# ---------------------------
openai.api_key = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "YOUR_AIRTABLE_API_KEY_HERE")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "YOUR_AIRTABLE_BASE_ID_HERE")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Documents")
# ---------------------------

logging.basicConfig(level=logging.INFO)
BASE_URL = "https://www.cia.gov"

app = Flask(__name__)

# Set up Airtable connection
table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

# ---------------------------
# DATABASE FUNCTIONS (Using Airtable)
# ---------------------------
def store_document(title, url, report, summary, video_script, video_file):
    # Check if the document already exists in Airtable
    records = table.all(formula=f"{{url}} = '{url}'")
    if not records:
        data = {
            "title": title,
            "url": url,
            "report": report,
            "summary": summary,
            "video_script": video_script,
            "video_file": video_file,
            "processed_at": datetime.now().isoformat()
        }
        table.create(data)

def search_documents(keyword, start_date, end_date):
    # Build a formula to search by keyword in title, report, or summary.
    formula_parts = []
    if keyword:
        # Escape single quotes if necessary.
        keyword = keyword.replace("'", "\\'")
        formula_parts.append(f"FIND('{keyword}', {{title}})")
        formula_parts.append(f"FIND('{keyword}', {{report}})")
        formula_parts.append(f"FIND('{keyword}', {{summary}})")
        search_formula = "OR(" + ", ".join(formula_parts) + ")"
    else:
        search_formula = ""
    # Date filtering
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
    return table.all(formula=formula) if formula else table.all()

# ---------------------------
# SCRAPING & SEARCH FUNCTIONS
# ---------------------------
def build_cia_search_url(keyword, start_date, end_date):
    # Convert dates to format: YYYY-MM-DDT00%3A00%3A00Z
    start_str = f"{start_date}T00%3A00%3A00Z" if start_date else "1900-01-01T00%3A00%3A00Z"
    end_str   = f"{end_date}T00%3A00%3A00Z"   if end_date else "2100-01-01T00%3A00%3A00Z"
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
    # Replace with a real API call:
    return "Detailed report (placeholder)."

def call_chatgpt_summary(report):
    prompt = f"Provide a bullet-point summary for the following detailed report:\n\n{report}"
    return "Bullet-point summary (placeholder)."

def call_video_script(report):
    prompt = f"Convert the following detailed report into a video script for a 5-minute faceless YouTube video:\n\n{report}"
    return "Video script (placeholder)."

def split_script_into_segments(script, segment_duration=5):
    sentences = script.split('.')
    segments = [s.strip() for s in sentences if s.strip()]
    return segments

def generate_image_for_segment(segment_text):
    # Using Midjourney is manual or through a Discord bot typically.
    # For this placeholder, return a placeholder image URL.
    return "https://via.placeholder.com/512"

def generate_images_for_script(script):
    segments = split_script_into_segments(script)
    image_urls = []
    for segment in segments:
        img_url = generate_image_for_segment(segment)
        image_urls.append(img_url)
        time.sleep(1)
    return image_urls

def create_video_from_images(image_urls, segment_duration=5, output_filename="output_video.mp4"):
    clips = []
    for img_url in image_urls:
        # Note: If img_url is a remote URL, you must download the image and save locally first.
        clip = ImageClip(img_url).set_duration(segment_duration)
        clips.append(clip)
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(output_filename, fps=24)
    return output_filename

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
            image_urls = generate_images_for_script(video_script)
            video_file = create_video_from_images(image_urls)
            store_document(doc_title, doc_url, report, summary, video_script, video_file)
            return {"report": report, "summary": summary, "video_script": video_script, "video_file": video_file}
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
                        "report": "Already in DB or no link found",
                        "summary": "",
                        "video_script": "",
                        "video_file": ""
                    })
                time.sleep(1)
            current_url = get_next_page_url(soup)
        return render_template("search_cia.html", results=results, keyword=keyword, start_date=start_date, end_date=end_date)
    else:
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
    else:
        return jsonify({"error": "Processing failed."}), 500

# ---------------------------
# MAIN EXECUTION
# ---------------------------
if __name__ == "__main__":
    # Initialize Airtable (data will be stored there)
    # Start the daily update scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_update, 'interval', days=1, next_run_time=datetime.now() + timedelta(seconds=10))
    scheduler.start()
    app.run(debug=True)

