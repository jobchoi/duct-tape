import os
import tempfile
import sys
import pandas as pd
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# -----------------------------
# 한글 폰트 등록
# -----------------------------
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
FONT_NAME = 'HYSMyeongJo-Medium'

# -----------------------------
# Formtec 3108 규격 (단위: points)
# -----------------------------
# 1mm = 2.83465 points
MM_TO_PT = 2.83465

PAGE_WIDTH, PAGE_HEIGHT = A4
LABEL_WIDTH = 99.1 * MM_TO_PT
LABEL_HEIGHT = 38.1 * MM_TO_PT

COLS = 2
ROWS = 7

LEFT_MARGIN = 6 * MM_TO_PT
TOP_MARGIN = 15 * MM_TO_PT  # 상단 여백
H_GAP = 2 * MM_TO_PT        # 라벨 간 좌우 간격
V_GAP = 0 * MM_TO_PT        # 3108은 보통 상하 간격이 없음

# -----------------------------
# 데이터 읽기
# -----------------------------
df = pd.read_excel('data.xlsx')
df.columns = df.columns.str.strip()

# -----------------------------
# PDF 생성
# -----------------------------
pdf_file = 'formtec_3108_labels_fixed.pdf'
c = canvas.Canvas(pdf_file, pagesize=A4)

for idx, row in df.iterrows():
    # 페이지당 라벨 개수 계산 (14개)
    items_per_page = COLS * ROWS
    page_index = idx % items_per_page

    # 14개를 다 채우면 새 페이지 생성
    if idx > 0 and page_index == 0:
        c.showPage()

    col = page_index % COLS
    row_num = page_index // COLS

    # X, Y 좌표 계산 (Y는 아래에서 위로 올라가는 방식임을 주의)
    x = LEFT_MARGIN + col * (LABEL_WIDTH + H_GAP)
    y = PAGE_HEIGHT - TOP_MARGIN - ((row_num + 1) * LABEL_HEIGHT)

    serial = str(row['serial'])
    user = str(row['user'])
    qr_data = f'{serial}'

    # QR 생성
    qr = qrcode.make(qr_data)
    temp_qr = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    qr.save(temp_qr.name)

    # -----------------------------
    # QR 배치 (왼쪽 정렬)
    # -----------------------------
    qr_size = 75  # 크기를 살짝 키움
    qr_x_offset = 10
    qr_y_offset = (LABEL_HEIGHT - qr_size) / 2 # 라벨 높이 중앙 배치

    c.drawImage(
        ImageReader(temp_qr.name),
        x + qr_x_offset,
        y + qr_y_offset,
        width=qr_size,
        height=qr_size
    )

    # -----------------------------
    # 텍스트 배치 (QR 오른쪽으로 가깝게 조정)
    # -----------------------------
    # QR 코드 끝나는 지점 근처로 텍스트 시작점 변경
    text_start_x = x + qr_x_offset + qr_size + 15 
    center_y = y + (LABEL_HEIGHT / 2)

    # 이름 (좌측 정렬로 변경하여 가독성 높임)
    c.setFont(FONT_NAME, 12)
    c.drawString(
        text_start_x,
        center_y + 5,
        f"사용자: {user}"
    )

    # 시리얼
    c.setFont(FONT_NAME, 9)
    c.drawString(
        text_start_x,
        center_y - 10,
        f"S/N: {serial}"
    )

    # 임시 파일 삭제 준비 (운영체제에 따라 닫은 후 삭제)
    temp_qr.close()

# PDF 저장
c.save()

print(f'완료: {pdf_file}')