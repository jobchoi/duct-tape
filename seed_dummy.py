import requests
import random
import uuid
from datetime import datetime, timezone

API_URL = "http://localhost:8000/api/report"

# 학교별 등록된 토큰 매핑
SCHOOL_TOKENS = {
    "SCH-HS-01": "school_token_hs01_secret_1234567890_ab",
    "SCH-MS-02": "school_token_ms02_secret_1234567890_cd",
    "SCH-ELEM-03": "school_token_elem03_secret_123456789_ef"
}

models = ["Galaxy Book 4", "LG gram 15", "Lenovo ThinkPad L13"]
stages = ['Preflight', '01', '02', '03', '04', '05', '06']
install_states = ['확인 전', '설치 필요', '설치 중', '정상', '오류']
statuses = ['running', 'completed', 'completed', 'failed'] # completed 비중 높임

print(">> 엄격 스키마 준수: 50대 탭북 더미 데이터 전송 시작...")

for i in range(1, 51):
    school = random.choice(list(SCHOOL_TOKENS.keys()))
    token = SCHOOL_TOKENS[school]
    
    # grade는 int (strict=True, 1~6)
    grade_int = random.randint(1, 6) if "ELEM" in school else random.randint(1, 3)
    status_val = random.choice(statuses)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "school_code": school,
        "grade": grade_int,
        "device_id": str(uuid.uuid4()),
        "report_id": str(uuid.uuid4()),
        "hostname": f"TAB-{school.split('-')[1]}-{i:02d}",
        "serial": f"SN-{random.randint(100000, 999999)}",
        "model": random.choice(models),
        "mac": f"00:1A:2B:3C:4D:{i:02X}",
        "office": "정상" if status_val == "completed" else "설치 중",
        "hancom": "정상" if status_val == "completed" else "확인 전",
        "stage": "06" if status_val == "completed" else random.choice(stages),
        "status": status_val,
        "error_code": "ERR_1603" if status_val == "failed" else "",
        "installer_exit_code": 1603 if status_val == "failed" else 0,
        "reboot_required": False,
        "observed_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        res = requests.post(API_URL, json=payload, headers=headers, timeout=2)
        print(f"[{i:02d}/50] {payload['hostname']} ({school}) -> 응답: {res.status_code}")
        if res.status_code != 200 and res.status_code != 201:
            print(f"   에러 상세: {res.text}")
    except Exception as e:
        print(f"[{i:02d}/50] 통신 실패: {e}")

print(">> 전송 완료!")
