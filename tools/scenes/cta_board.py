# -*- coding: utf-8 -*-
"""엔딩·CTA 시안 6장(정지) — 2편 실제 장면으로 1080×1920 목업 → 한 판(3×2)."""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\user\Desktop\숏폼자동화\tools")
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402
import s6_render as R  # noqa: E402

SRC = "D:/26년 10월/261006/쇼츠자동화/빡이사DB.mp4"
OUT = Path(r"C:\Users\user\Desktop\숏폼자동화\납품\빡이사DB_쇼츠\_엔딩CTA시안")
OUT.mkdir(parents=True, exist_ok=True)
W, H, TOP, BOT, CH = R.W, R.H, R.TOP, R.BOT, R.CH
title = ["DB계약률 90%", "고객 관리 꿀팁"]
bar = R.title_bar(title)

face_big = R.still(SRC, 2361.2, [613, 290, 574, 675])          # 39:22 큰 얼굴 — 간판(y 135~270) 아래·구운 자막(y 975~) 위
face_sq = R.still(SRC, 2361.2, [620, 295, 560, 560])            # 원형용 정사각
pip = R.still(SRC, 1674.5, [19, 778, 292, 292])                  # 2편 끝 PIP 원
preview = R.still(SRC, 1673.0, [1180, 250, 500, 590]).resize((W, 1274), Image.LANCZOS)


def circle(img, d, ring=(255, 255, 255), rw=10):
    img = img.resize((d, d), Image.LANCZOS)
    m = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(m).ellipse([0, 0, d * 4 - 1, d * 4 - 1], fill=255)
    m = m.resize((d, d), Image.LANCZOS)
    out = Image.new("RGBA", (d + rw * 2, d + rw * 2), (0, 0, 0, 0))
    rm = m.resize((d + rw * 2, d + rw * 2), Image.LANCZOS)
    out.paste(Image.new("RGBA", out.size, ring + (255,)), (0, 0), rm)
    out.paste(img, (rw, rw), m)
    return out


def base(content):
    fr = Image.new("RGB", (W, H), (0, 0, 0))
    fr.paste(content, (0, TOP))
    fr.paste(bar, (0, 0))
    return fr


def cap(fr, text, hl=None, y=R.CAP_Y):
    ci = R.caption_img(text, hl)
    fr.paste(ci, ((W - ci.width) // 2, y - ci.height // 2), ci)


def chip(d, xy, text, fill, fg=(255, 255, 255), size=44, pad=(26, 14)):
    f = R.font(R.FONT_XB, size)
    w = int(f.getlength(text))
    x, y = xy
    d.rounded_rectangle([x, y, x + w + pad[0] * 2, y + size + pad[1] * 2], 999, fill=fill)
    d.text((x + pad[0], y + pad[1] - 4), text, font=f, fill=fg)
    return w + pad[0] * 2


boards = []

# 1 검은 무대 + 원(사장님 언급) — 원 둘레 노란 링, 아래 이름표
c = Image.new("RGB", (W, CH), (14, 14, 16))
g = Image.new("RGB", (W, CH), (14, 14, 16))
ImageDraw.Draw(g).ellipse([140, 60, 940, 860], fill=(40, 40, 46))
c = Image.blend(c, g.filter(ImageFilter.GaussianBlur(90)), 1.0)
cc = circle(face_sq, 700, ring=(255, 212, 0), rw=8)
c.paste(cc, ((W - cc.width) // 2, 110), cc)
d = ImageDraw.Draw(c)
fr = base(c)
cap(fr, "거부감이 좀 덜합니다", "거부감")
boards.append(("① 검은 무대 + 얼굴 원", "사장님 말씀 그대로. 밝은 배경 위 원보다 집중감↑, 노란 링 = 제목 강조색과 통일", fr))

# 2 풀스크린 얼굴(39:20 큰 얼굴 실제 영상) + 실제 CTA 대사 자막
fb = face_big.resize((int(574 * CH / 675), CH), Image.LANCZOS)
fb = fb.crop(((fb.width - W) // 2, 0, (fb.width - W) // 2 + W, CH))
fr = base(fb)
cap(fr, "필요한 업종 댓글 남겨주세요", "댓글")
boards.append(("② 대표 큰 얼굴 + 실제 CTA 목소리", "롱폼 39:20 «필요한 업종 … 댓글 남겨주세요»(원본 화질). 모든 편 끝 3~4초 공통 꼬리", fr))

# 3 위 자료 / 아래 얼굴(슈카 자료칸+웹캠 문법)
c = Image.new("RGB", (W, CH), (236, 240, 244))
pv = preview.crop((0, 380, W, 380 + 760))
c.paste(pv, (0, 0))
fc = face_big.resize((W, int(675 * W / 574)), Image.LANCZOS).crop((0, 110, W, 110 + CH - 760))
c.paste(fc, (0, 760))
fr = base(c)
cap(fr, "거부감이 좀 덜합니다", "거부감", y=TOP + 760 - 70)
boards.append(("③ 위 자료 · 아래 얼굴(분할)", "슈카월드 상위 4/6 문법 — 결론 순간 자료와 말하는 사람을 같이. 원 없음", fr))

# 4 결론 키워드 카드 + 작은 얼굴(박곰희 2단 카드)
c = Image.new("RGB", (W, CH), (236, 240, 244))
fbb = face_big.resize((W, int(675 * W / 574)), Image.LANCZOS)
fbb = fbb.resize((int(W * CH / fbb.height), CH), Image.LANCZOS) if fbb.height < CH else fbb.crop((0, 0, W, CH))
fbb = fbb.crop(((fbb.width - W) // 2, 0, (fbb.width - W) // 2 + W, CH))
c.paste(fbb, (0, 0))
d = ImageDraw.Draw(c)
d.rounded_rectangle([70, 70, W - 70, 430], 26, fill=(255, 255, 255))
chip(d, (110, 105), "핵심 정리", (30, 90, 220), size=36)
fT = R.font(R.FONT_XB, 78)
d.text((W // 2, 260), "'상담 신청' 말고", font=fT, fill=(30, 30, 34), anchor="mm")
d.text((W // 2, 360), "'1분 상담 신청'", font=fT, fill=(30, 90, 220), anchor="mm")
fr = base(c)
cap(fr, "거부감이 좀 덜합니다", "거부감")
boards.append(("④ 결론 카드 + 얼굴", "박곰희식 «라벨 칩 + 큰 제목» 2단. 영상의 결론을 한 장으로 남김 → 저장·공유 유도", fr))

# 5 다음 편 예고(시리즈 넘버링) — 정주행 유도
c = Image.new("RGB", (W, CH), (14, 14, 16))
cc = circle(face_sq, 420, ring=(255, 255, 255), rw=6)
c.paste(cc, ((W - cc.width) // 2, 70), cc)
d = ImageDraw.Draw(c)
chip(d, (W // 2 - 150, 560), "메타 광고 세팅 2/8", (255, 212, 0), fg=(20, 20, 20), size=40)
d.rounded_rectangle([90, 680, W - 90, 900], 24, fill=(34, 34, 40))
d.text((140, 712), "다음 편", font=R.font(R.FONT_B, 40), fill=(170, 170, 180))
d.text((140, 770), "대박나는 광고영상 만드는 법", font=R.font(R.FONT_XB, 58), fill=(255, 255, 255))
fr = base(c)
cap(fr, "거부감이 좀 덜합니다", "거부감")
boards.append(("⑤ 다음 편 예고(시리즈)", "8편 연재로 묶어 «2/8 · 다음 편» — 채널 성장(정주행·구독) 목적에 맞춤. 말 없이 화면만", fr))

# 6 댓글 유도 말풍선 + 얼굴(실제 대사와 짝)
c = Image.new("RGB", (W, CH), (236, 240, 244))
c.paste(fbb, (0, 0))
d = ImageDraw.Draw(c)
d.rounded_rectangle([80, 90, W - 80, 330], 34, fill=(255, 255, 255))
d.polygon([(W // 2 - 30, 328), (W // 2 + 30, 328), (W // 2, 372)], fill=(255, 255, 255))
d.text((W // 2, 160), "우리 업종은 어떻게 세팅하죠?", font=R.font(R.FONT_XB, 56), fill=(30, 30, 34), anchor="mm")
d.text((W // 2, 250), "댓글에 업종 남기면 답 드립니다", font=R.font(R.FONT_B, 46), fill=(30, 90, 220), anchor="mm")
fr = base(c)
cap(fr, "댓글 남겨주세요", "댓글")
boards.append(("⑥ 댓글 질문 말풍선", "시청자 질문형(마코장·박곰희 상위 공통) + 대표 실제 약속 «하나하나 답해 드릴게요»(39:01)", fr))

# 한 판
tw, th = 360, 640
sheet = Image.new("RGB", (tw * 3 + 80, (th + 170) * 2 + 40), (245, 245, 245))
d = ImageDraw.Draw(sheet)
for i, (name, why, fr) in enumerate(boards):
    fr.save(OUT / f"CTA{i + 1}.png")
    x = 20 + (i % 3) * (tw + 20)
    y = 20 + (i // 3) * (th + 170)
    sheet.paste(fr.resize((tw, th), Image.LANCZOS), (x, y))
    d.text((x, y + th + 10), name, font=R.font(R.FONT_XB, 26), fill=(20, 20, 20))
    words, line, yy = why.split(" "), "", y + th + 48
    for w_ in words:
        if R.font(R.FONT_B, 19).getlength(line + w_) > tw:
            d.text((x, yy), line, font=R.font(R.FONT_B, 19), fill=(80, 80, 80))
            yy, line = yy + 26, ""
        line += w_ + " "
    d.text((x, yy), line, font=R.font(R.FONT_B, 19), fill=(80, 80, 80))
sheet.save(OUT / "_엔딩CTA_6안.png")
print("ok", OUT)
