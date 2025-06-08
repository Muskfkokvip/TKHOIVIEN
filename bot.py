import os
import re
import io
import traceback
import pandas as pd
import gspread
from aiogram import Bot, Dispatcher, types, executor
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# === Tải các biến môi trường từ .env ===
load_dotenv()

# === Cấu hình bot Telegram ===
API_TOKEN = os.getenv('API_TOKEN')  # Token bot từ biến môi trường
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# === Đọc danh sách từ Google Sheets ===
def load_received_accounts():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_json = os.getenv('SERVICE_ACCOUNT_JSON')  # Lấy thông tin service account từ biến môi trường
        creds = ServiceAccountCredentials.from_json_keyfile_dict(eval(creds_json), scope)  # Chuyển chuỗi JSON thành dictionary
        client = gspread.authorize(creds)

        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1GSE0XHi-oz-3MDU-ygo-Y2NVosMsLm53zBi3JjAcPvw/edit?gid=1694691629")
        worksheet = sheet.worksheet("sheet1")

        data = [row[0] for row in worksheet.get_all_values() if row and row[0].strip()]
        return set(re.sub(r'\s+', '', cell.strip().lower()) for cell in data)  # Chuẩn hóa dữ liệu trong Google Sheets
    except Exception as e:
        print("Lỗi khi đọc Google Sheet:")
        traceback.print_exc()
        return set()

# === Chuẩn hóa tài khoản ===
def normalize_account(acc):
    return re.sub(r'\s+', '', acc.strip().lower())  # Loại bỏ khoảng trắng thừa và chuyển thành chữ thường

# === Phân tích văn bản/tài khoản ===
def parse_accounts(text):
    text = text.strip()
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
    else:
        parts = [line.strip() for line in text.splitlines() if line.strip()]
    pattern = re.compile(r"[a-zA-Z0-9_]+")
    filtered = []
    for p in parts:
        m = pattern.findall(p)
        if m:
            filtered.append(normalize_account("".join(m)))
    return filtered

# === Xuất danh sách ra file Excel ===
def export_excel(account_list, filename):
    df = pd.DataFrame({
        "STT": range(1, len(account_list) + 1),
        "Tài khoản": account_list
    })
    df.to_excel(filename, index=False)

# === Gửi kết quả lọc về Telegram ===
async def send_summary(message, input_accounts, matched, unmatched):
    total = len(input_accounts)
    summary = (
        f"📋 Đã lọc thành công: {total} tài khoản\n"
        f"❌ Tài khoản đã nhận code: {len(matched)}\n"
        f"✅ Tài khoản chưa nhận code: {len(unmatched)}"
    )
    await message.reply(summary)

    if len(unmatched) >= 200:
        await message.reply("✅ Đủ số lượng tài khoản hợp lệ, không thể nhận thêm.")
        return

    if 0 < len(matched) <= 50:
        line = ",".join(matched)
        await message.reply(f"❌ Danh sách đã nhận:\n{line}")
    elif len(matched) > 50:
        export_excel(matched, "danhan.xlsx")
        await message.reply_document(types.InputFile("danhan.xlsx"), caption="❌ Danh sách đã nhận")

    if unmatched:
        export_excel(unmatched, "chuanhan.xlsx")
        await message.reply_document(types.InputFile("chuanhan.xlsx"), caption="✅ Danh sách chưa nhận")

# === Xử lý văn bản trực tiếp ===
@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_text(message: types.Message):
    input_accounts = parse_accounts(message.text)
    if not input_accounts:
        await message.reply("Không tìm thấy tài khoản hợp lệ.")
        return

    # Chuẩn hóa tài khoản gửi lên
    received_accounts = load_received_accounts()

    # So sánh tài khoản đã nhận và chưa nhận
    matched = [acc for acc in input_accounts if normalize_account(acc) in received_accounts]
    unmatched = [acc for acc in input_accounts if normalize_account(acc) not in received_accounts]

    await send_summary(message, input_accounts, matched, unmatched)

# === Xử lý file gửi lên ===
@dp.message_handler(content_types=[types.ContentType.DOCUMENT])
async def handle_document(message: types.Message):
    document = message.document
    file_name = document.file_name.lower()
    file = await document.download(destination=io.BytesIO())
    file.seek(0)
    input_accounts = []

    try:
        if file_name.endswith(".txt") or file_name.endswith(".csv"):
            content = file.read().decode("utf-8")
            input_accounts = parse_accounts(content)
        elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
            df = pd.read_excel(file, dtype=str, engine='openpyxl')
            df = df.applymap(lambda x: normalize_account(x) if isinstance(x, str) else '')
            vals = df.values.flatten().tolist()
            input_accounts = [acc for acc in vals if acc]
        elif file_name.endswith(".docx"):
            import docx
            doc = docx.Document(file)
            for p in doc.paragraphs:
                if p.text.strip():
                    input_accounts.extend(parse_accounts(p.text))
        else:
            await message.reply("Định dạng file không được hỗ trợ.")
            return
    except Exception as e:
        await message.reply(f"Lỗi khi xử lý file: {e}")
        return

    if not input_accounts:
        await message.reply("Không tìm thấy tài khoản hợp lệ trong file.")
        return

    # Chuẩn hóa tài khoản gửi lên
    received_accounts = load_received_accounts()

    # So sánh tài khoản đã nhận và chưa nhận
    matched = [acc for acc in input_accounts if normalize_account(acc) in received_accounts]
    unmatched = [acc for acc in input_accounts if normalize_account(acc) not in received_accounts]

    await send_summary(message, input_accounts, matched, unmatched)

# === Khởi động bot ===
if __name__ == '__main__':
    print("🤖 Bot đang chạy và đối chiếu dữ liệu với Google Sheets...")
    executor.start_polling(dp, skip_updates=True)
