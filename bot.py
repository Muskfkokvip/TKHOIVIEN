SN MUSK - OKVIP, [07/06/2025 9:01 CH]
import os
import logging
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from docx import Document as DocxDocument
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load biến môi trường từ .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Cấu hình Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)

# Mở Google Sheet "CHECK CODE HÒM THƯ", sheet "Sheet1"
spreadsheet = client.open("CHECK CODE HÒM THƯ")
sheet = spreadsheet.worksheet("Sheet1")

logging.basicConfig(level=logging.INFO)

def extract_text_from_file(file_bytes: BytesIO, mime: str) -> str:
    try:
        if "text" in mime:
            return file_bytes.read().decode("utf-8", errors="ignore")
        elif "msword" in mime or "officedocument.wordprocessingml" in mime:
            doc = DocxDocument(file_bytes)
            return "\n".join([p.text for p in doc.paragraphs])
        elif "spreadsheetml" in mime:
            df = pd.read_excel(file_bytes)
            # lấy toàn bộ cột đầu tiên nối thành chuỗi
            return "\n".join(df.iloc[:, 0].astype(str).dropna())
        else:
            return ""
    except Exception as e:
        logging.error(f"extract_text_from_file error: {e}")
        return ""

def parse_accounts(text: str):
    # Tách theo dòng, dấu phẩy, xóa trắng, loại trùng giữ thứ tự
    lines = [line.strip() for line in text.replace(",", "\n").splitlines() if line.strip()]
    unique_accounts = list(dict.fromkeys(lines))
    return unique_accounts

def filter_accounts_from_sheet(accounts):
    sheet_data = sheet.col_values(1)  # Cột A trong Google Sheet
    received = [acc for acc in accounts if acc in sheet_data]
    not_received = [acc for acc in accounts if acc not in sheet_data]
    return received, not_received

async def process_and_reply(update: Update, raw_text: str):
    accounts = parse_accounts(raw_text)
    if len(accounts) == 0:
        await update.message.reply_text("❌ Không tìm thấy tài khoản hợp lệ để lọc.")
        return

    received, not_received = filter_accounts_from_sheet(accounts)

    response = f"📋 Đã lọc: {len(accounts)} tài khoản\n"
    response += f"❌ Tài khoản đã nhận: {len(received)}\n"
    response += f"✅ Tài khoản hợp lệ chưa nhận: {len(not_received)}\n"

    target = 200
    if len(not_received) == target:
        response += f"✅ Đã đủ số lượng {target} tài khoản hợp lệ chưa nhận."
    elif len(not_received) > target:
        response += f"⚠️ Thừa {len(not_received)-target} tài khoản hợp lệ chưa nhận."
    else:
        response += f"⚠️ Thiếu {target - len(not_received)} tài khoản hợp lệ chưa nhận."

    await update.message.reply_text(response)

    if len(not_received) == 0:
        await update.message.reply_text("ℹ️ Không có tài khoản chưa nhận để xuất file XLSX.")
        return

    # Tạo file XLSX chỉ chứa tài khoản chưa nhận
    df = pd.DataFrame({"Tài khoản chưa nhận": not_received})
    xlsx_file = BytesIO()
    with pd.ExcelWriter(xlsx_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    xlsx_file.seek(0)
    xlsx_file.name = "tai_khoan_chua_nhan.xlsx"

    await update.message.reply_document(document=xlsx_file)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Xử lý cả tin nhắn chuyển tiếp
    text = update.message.text or ""
    if not text.strip():
        await update.message.reply_text("❌ Tin nhắn rỗng, vui lòng gửi dữ liệu hợp lệ.")
        return
    await process_and_reply(update, text)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    if not file:
        await update.message.reply_text("❌ Không nhận được file hợp lệ.")
        return

SN MUSK - OKVIP, [07/06/2025 9:01 CH]
file_obj = await file.get_file()
    file_bytes = BytesIO()
    await file_obj.download(out=file_bytes)
    file_bytes.seek(0)

    content = extract_text_from_file(file_bytes, file.mime_type)
    if not content.strip():
        await update.message.reply_text("❌ Không đọc được nội dung từ file.")
        return

    await process_and_reply(update, content)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Gửi danh sách tài khoản (text hoặc file) để bot lọc.\n"
                                    "- Hỗ trợ file: .xlsx, .docx, .txt\n"
                                    "- Tài khoản cách nhau dấu phẩy hoặc xuống dòng.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if name == "main":
    main()
