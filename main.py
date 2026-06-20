from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import os, time, shutil, tempfile, requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image, ImageOps

app = FastAPI(root_path="/mathflat")

# --- 데이터 모델 ---
class LoginRequest(BaseModel):
    user_id: str
    password: str
    worksheet_index: int = 1  # 몇 번째 학습지를 받을지 (기본 1번)


# --- PDF 추출 핵심 로직 ---
def run_mathflat_extraction(user_id, password, worksheet_idx, download_path):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 20)
    session = requests.Session()

    try:
        # 1. 로그인
        driver.get("https://student.mathflat.com/#/login")
        id_input = wait.until(EC.presence_of_element_located((By.NAME, "id")))
        id_input.send_keys(user_id)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button.submit-button").click()

        # 로그인 완료 대기
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.card-list")))
        
        for cookie in driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])

        # 2. 학습지 목록 분석 및 선택
        cards = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//ul[@class='card-list']/li/a")))
        if len(cards) < worksheet_idx:
            raise Exception("선택한 번호의 학습지가 존재하지 않습니다.")
        
        target_card = cards[worksheet_idx - 1]
        try:
            worksheet_title = target_card.find_element(By.CSS_SELECTOR, "p.title").text.strip()
        except:
            worksheet_title = f"학습지_{worksheet_idx}"
        print(worksheet_title)
        driver.execute_script("arguments[0].click();", target_card)

        driver.get(driver.current_url + "/scoring")

        switch = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "label.ms__switch_switch")))
        driver.execute_script("arguments[0].click();", switch)
        # 3. 이미지 추출 및 PDF 생성
        img_tags = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img.problem-image")))
        print(img_tags)
        processed_images = []
        
        for idx, tag in enumerate(img_tags):
            src = tag.get_attribute("src")
            alt = tag.get_attribute("alt") or ""
            if not src or "answer" in src or "정답" in alt: continue

            res = session.get(src)
            if res.status_code == 200:
                img = Image.open(requests.get(src, stream=True).raw).convert("RGB")
                img_with_margin = ImageOps.expand(img, border=250, fill='white')
                processed_images.append(img_with_margin)

        if not processed_images:
            raise Exception("문제를 찾을 수 없습니다.")

        # PDF 저장
        processed_images[0].save(download_path, save_all=True, append_images=processed_images[1:])
        return worksheet_title

    finally:
        driver.quit()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/download-pdf")
async def download_pdf(request: LoginRequest, background_tasks: BackgroundTasks):
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "result.pdf")

    try:
        # 이전에 완성한 추출 함수 호출
        # (테스트를 위해 추출 함수가 성공했다고 가정하는 로직을 구현해야 함)
        worksheet_title = run_mathflat_extraction(request.user_id, request.password, request.worksheet_index, file_path)
        
        if worksheet_title and os.path.exists(file_path):
            background_tasks.add_task(shutil.rmtree, tmp_dir)
            return FileResponse(path=file_path, filename=f"{worksheet_title}.pdf", media_type='application/pdf')
        else:
            raise Exception("PDF 생성 실패")
    except Exception as e:
        if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
        raise HTTPException(status_code=400, detail=str(e))