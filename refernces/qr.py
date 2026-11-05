import os
import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

def generate_smart_labels():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_csv = os.path.join(script_dir, 'data.csv')
    output_pdf = os.path.join(script_dir, 'formtec_3108_smart.pdf')

    # 한글 폰트 설정
    font_path = "C:/Windows/Fonts/malgun.ttf"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Malgun', font_path))
        FONT_NAME = 'Malgun'
    else:
        FONT_NAME = 'Helvetica'

    if not os.path.exists(input_csv):
        print(f"🚨 [오류] {script_dir} 경로에 'data.csv' 파일이 없습니다.")
        return

    with open(input_csv, 'r', encoding='utf-8-sig', errors='ignore') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    if len(lines) < 2:
        print("🚨 [오류] CSV 파일에 데이터가 없습니다.")
        return

    header_line = lines[0]
    delimiter = '\t' if '\t' in header_line else ','
    headers = [h.strip() for h in header_line.split(delimiter)]

    name_idx, sn_idx = -1, -1
    for i, h in enumerate(headers):
        if '이름' in h: name_idx = i
        if 'S/N' in h.upper() or 'SN' in h.upper(): sn_idx = i

    if name_idx == -1 or sn_idx == -1:
        print("\n🚨 [오류] 엑셀 첫 줄에서 '이름' 또는 'S/N' 카테고리를 찾지 못했습니다!")
        return

    # --- 💡 사용자 입력 옵션 (전체 vs 지정 위치) ---
    print("=" * 60)
    year_input = input("1. 입학년도를 입력하세요 [엔터 시 '2026' 자동 적용]: ").strip()
    admission_year = year_input if year_input else "2026"
    print("-" * 60)
    
    print("[안내] 쓰다 남은 라벨지에 특정 인원만 골라서 인쇄할 수 있습니다.")
    names_input = input("2. 출력할 이름을 쉼표(,)로 입력 (전체 인쇄 시 그냥 엔터): ").strip()
    
    target_names = []
    target_positions = []
    
    if names_input:
        target_names = [n.strip() for n in names_input.split(",")]
        pos_input = input(f"3. 위 {len(target_names)}명이 출력될 라벨 번호(1~14)를 쉼표(,)로 입력: ").strip()
        
        try:
            target_positions = [int(p.strip()) for p in pos_input.split(",")]
        except ValueError:
            print("🚨 [오류] 라벨 번호는 반드시 숫자로 입력해야 합니다.")
            return
            
        if len(target_names) != len(target_positions):
            print(f"🚨 [오류] 입력한 이름 수({len(target_names)}명)와 위치 수({len(target_positions)}개)가 다릅니다!")
            return
            
    print("=" * 60)
    print("PDF 생성을 시작합니다...\n")
    # ----------------------------------------------
    
    # 출력할 데이터 수집
    data_to_print = []
    
    if target_names:
        # 부분 인쇄 모드 (입력한 순서와 위치 매칭)
        for i, target_name in enumerate(target_names):
            found = False
            for line in lines[1:]:
                cols = [col.strip() for col in line.split(delimiter)]
                if len(cols) > max(name_idx, sn_idx) and cols[name_idx] == target_name:
                    data_to_print.append({
                        "name": cols[name_idx], 
                        "sn": cols[sn_idx], 
                        "pos": target_positions[i]
                    })
                    found = True
                    break
            if not found:
                print(f"⚠️ 경고: '{target_name}' 님의 데이터를 엑셀에서 찾지 못했습니다.")
    else:
        # 전체 인쇄 모드 (1번부터 순차적으로 자동 번호 부여)
        current_pos = 1
        for line in lines[1:]:
            cols = [col.strip() for col in line.split(delimiter)]
            if len(cols) > max(name_idx, sn_idx) and cols[name_idx] and cols[sn_idx]:
                data_to_print.append({
                    "name": cols[name_idx], 
                    "sn": cols[sn_idx], 
                    "pos": current_pos
                })
                current_pos += 1

    if not data_to_print:
        print("🚨 [오류] 출력할 유효한 데이터가 없습니다.")
        return

    # 라벨 번호(pos) 순서대로 정렬 (페이지 꼬임 방지)
    data_to_print.sort(key=lambda x: x['pos'])

    c = canvas.Canvas(output_pdf, pagesize=A4)
    
    # 폼텍 14칸(99.1 x 38.1 mm) 정밀 규격
    LABEL_WIDTH, LABEL_HEIGHT = 99.1 * mm, 38.1 * mm
    MARGIN_LEFT, MARGIN_TOP = 4.7 * mm, 15.1 * mm
    GAP_X = 2.5 * mm
    
    current_page = 0
    
    for entry in data_to_print:
        pos_num = entry['pos']
        
        # 페이지 계산 (14칸을 넘어가면 새 페이지 생성)
        target_page = (pos_num - 1) // 14
        while current_page < target_page:
            c.showPage()
            current_page += 1
            
        # 수직 번호 체계 (1~7번 좌측, 8~14번 우측)
        pos_on_page = (pos_num - 1) % 14
        col = pos_on_page // 7
        row = pos_on_page % 7
        
        x = MARGIN_LEFT + col * (LABEL_WIDTH + GAP_X)
        y = A4[1] - MARGIN_TOP - ((row + 1) * LABEL_HEIGHT)
        
        # QR 생성
        qr = qrcode.QRCode(box_size=2, border=0)
        qr.add_data(f"{admission_year}|{entry['name']}|{entry['sn']}")
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = io.BytesIO()
        img_qr.save(qr_buffer)
        qr_buffer.seek(0)
        c.drawImage(ImageReader(qr_buffer), x + 5*mm, y + 5*mm, width=28*mm, height=28*mm)
        
        # 텍스트 출력
        c.setFont(FONT_NAME, 12)
        c.drawString(x + 38*mm, y + 24*mm, f"이름: {entry['name']}")
        
        c.setFont(FONT_NAME, 10)
        c.drawString(x + 38*mm, y + 15*mm, f"입학: {admission_year}년도")
        
        # S/N 잘림 방지용 8.5pt
        c.setFont(FONT_NAME, 8.5)
        c.drawString(x + 38*mm, y + 7*mm, f"S/N: {entry['sn']}")

    c.save()
    mode_text = "지정 위치" if target_names else "전체"
    print(f"✅ 완료! {mode_text} 라벨({len(data_to_print)}개)이 성공적으로 생성되었습니다.")
    print(f"✅ 결과 파일: {output_pdf}")

if __name__ == "__main__":
    generate_smart_labels()