import os
import json
from bs4 import BeautifulSoup

# 你的 GitHub Pages 目錄
ROOT = "."

index = []

for root, dirs, files in os.walk(ROOT):
    for file in files:
        if file.endswith(".html") and file not in ["index.html"]:
            full_path = os.path.join(root, file)
            
            # 網頁 URL（吉祥：https://taiwangoldfish.github.io/index/）
            url = full_path.replace("./", "").replace("\\", "/")
            
            with open(full_path, "r", encoding="utf-8") as f:
                html = f.read()
                soup = BeautifulSoup(html, "html.parser")
                
                # 擷取網頁標題
                title = soup.title.string if soup.title else url
                
                # 擷取全文純文字（不含 script/style）
                for s in soup(["script", "style"]):
                    s.extract()
                
                text = soup.get_text(separator=" ", strip=True)

                index.append({
                    "title": title,
                    "url": url,
                    "content": text
                })

# 寫入 JSON
with open("search-index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print("✅ search-index.json 產生成功！")
