#!/usr/bin/env python3
"""Xuất PDF đề cương từ Markdown và hai sơ đồ vector, giữ hỗ trợ chữ Việt."""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph,
                               SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
WIDTH = A4[0] - 100


def format_inline(value: str) -> str:
    value = html.escape(value).replace('&lt;br&gt;', '<br/>')
    value = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)',
                   r'<link href="\2" color="#243d54">\1</link>', value)
    value = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', value)
    value = re.sub(r'^\*(.+)\*$', r'<i>\1</i>', value)
    return value


class Diagram(Flowable):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.width = WIDTH
        self.height = 395 if kind == 'research' else 165
        self.style = ParagraphStyle('diagram', fontName='Body', fontSize=10.2,
                                    leading=12.2, alignment=TA_CENTER)

    def draw(self):
        c = self.canv

        def box(x, y, w, h, text, grey=False):
            c.setFillColor(colors.HexColor('#f1f3f5' if grey else '#edf4f8'))
            c.setStrokeColor(colors.HexColor('#667985'))
            c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
            p = Paragraph(text, self.style)
            _, ph = p.wrap(w-10, h-6)
            p.drawOn(c, x+5, y+(h-ph)/2)

        def arrow(points, dashed=False):
            c.setStrokeColor(colors.HexColor('#475569'))
            c.setFillColor(colors.HexColor('#475569'))
            c.setLineWidth(.8)
            c.setDash(3, 2) if dashed else c.setDash()
            for (a,b),(d,e) in zip(points,points[1:]):
                c.line(a,b,d,e)
            c.setDash()
            x,y=points[-1]; px,py=points[-2]
            dx,dy=x-px,y-py
            length=(dx*dx+dy*dy)**.5
            ux,uy=dx/length,dy/length
            path=c.beginPath(); path.moveTo(x,y)
            path.lineTo(x-5*ux+2.5*uy,y-5*uy-2.5*ux)
            path.lineTo(x-5*ux-2.5*uy,y-5*uy+2.5*ux)
            path.close(); c.drawPath(path,stroke=0,fill=1)

        if self.kind == 'research':
            box(0,350,135,38,'Nguồn dữ liệu<br/>và metadata')
            box(175,350,145,38,'Kiểm định, chuẩn hóa<br/>và căn chỉnh')
            box(375,350,120,38,'Chờ kiểm tra /<br/>cách ly',True)
            box(0,285,235,43,'Song ngữ đủ điều kiện<br/>Chia Train / Validation / Test')
            box(350,285,145,43,'Đơn ngữ đã kiểm định<br/>Tách khỏi validation/test')
            box(0,220,235,43,'Train gốc<br/>Huấn luyện baseline E0')
            box(350,220,145,43,'Dịch ngược<br/>Cố định mô hình sinh')
            box(350,160,145,40,'Dữ liệu tổng hợp U<br/>Chưa lọc QC nghiên cứu')
            box(350,95,145,43,'QC đầy đủ /<br/>bỏ riêng R1 hoặc R2')
            box(0,95,235,55,'Các cấu hình thực nghiệm<br/>E0 / E1 / E2 / E1-M / A1 / A2<br/>Cùng train gốc và khởi tạo')
            box(0,10,495,44,'Validation: chọn cấu hình/checkpoint<br/>Test cố định: đánh giá cuối và phân tích lỗi')
            arrow([(135,369),(175,369)])
            arrow([(320,369),(375,369)])
            arrow([(247,350),(247,338),(117,338),(117,328)])
            arrow([(247,338),(422,338),(422,328)])
            arrow([(117,285),(117,263)])
            arrow([(422,285),(422,263)])
            arrow([(235,241),(350,241)])
            arrow([(422,220),(422,200)])
            arrow([(117,220),(117,150)])
            arrow([(350,180),(270,180),(270,142),(235,142)])
            arrow([(422,160),(422,138)])
            arrow([(350,116),(235,116)])
            arrow([(117,95),(117,54)])
            arrow([(235,306),(255,306),(255,70),(320,70),(320,54)],True)
            c.setFont('Body',9)
            c.drawCentredString(347,377,'Chưa đạt')
            c.drawCentredString(292,248,'E0 chiều ngược')
            c.drawCentredString(177,181,'Giữ train gốc')
            c.drawCentredString(306,186,'E1, E1-M')
            c.drawCentredString(293,103,'E2, A1, A2')
            c.drawCentredString(347,76,'Tập đánh giá cố định')
        else:
            box(0,105,135,42,'Nhập văn bản<br/>và chọn chiều dịch')
            box(175,105,145,42,'Kiểm tra đầu vào<br/>và chiều hỗ trợ')
            box(365,105,130,42,'Suy luận dịch')
            box(0,25,135,42,'Cung cấp âm thanh<br/>trong phạm vi PoC')
            box(175,25,145,42,'ASR<br/>tạo transcript')
            box(365,25,130,42,'Hiển thị transcript<br/>và bản dịch / lỗi')
            arrow([(135,126),(175,126)])
            arrow([(320,126),(365,126)])
            arrow([(135,46),(175,46)])
            arrow([(247,67),(247,105)])
            arrow([(430,105),(430,67)])
            arrow([(320,46),(365,46)],True)


def build(source: Path, output: Path, font_dir: Path):
    for name,file in [('Body','FreeSerif.ttf'),('Body-Bold','FreeSerifBold.ttf'),('Body-Italic','FreeSerifItalic.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(font_dir/file)))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='Body-Bold',italic='Body-Italic',boldItalic='Body-Bold')
    body=ParagraphStyle('body',fontName='Body',fontSize=12,leading=15,
                        spaceAfter=6,alignment=TA_JUSTIFY)
    styles={
        'body':body,
        'h1':ParagraphStyle('h1',parent=body,fontName='Body-Bold',fontSize=16,leading=20,alignment=TA_CENTER,spaceBefore=9,spaceAfter=13,keepWithNext=True),
        'h2':ParagraphStyle('h2',parent=body,fontName='Body-Bold',fontSize=13.4,leading=17,spaceBefore=9,spaceAfter=7,keepWithNext=True),
        'h3':ParagraphStyle('h3',parent=body,fontName='Body-Bold',fontSize=12,leading=15.8,spaceBefore=5,spaceAfter=6,keepWithNext=True),
        'cell':ParagraphStyle('cell',parent=body,fontSize=10.5,leading=12,spaceAfter=0,alignment=0),
        'center':ParagraphStyle('center',parent=body,fontSize=11.3,leading=14,alignment=TA_CENTER,spaceAfter=0),
        'caption':ParagraphStyle('caption',parent=body,fontName='Body-Italic',fontSize=10.7,leading=13.3,alignment=TA_CENTER,spaceAfter=9),
        'bullet':ParagraphStyle('bullet',parent=body,leftIndent=11,firstLineIndent=-8,spaceAfter=5),
    }
    def p(text,style='body'): return Paragraph(format_inline(text),styles[style])
    header=Table([[p('ĐẠI HỌC QUỐC GIA TP. HỒ CHÍ MINH<br>**TRƯỜNG ĐẠI HỌC<br>CÔNG NGHỆ THÔNG TIN**','center'),
                   p('**CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM**<br>Độc lập – Tự do – Hạnh phúc','center')]],colWidths=[WIDTH*.46,WIDTH*.54])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),11)]))
    story=[header]
    lines=source.read_text(encoding='utf-8').splitlines()
    index=0
    while index<len(lines):
        line=lines[index].strip(); index+=1
        if not line: continue
        if line=='<!-- pagebreak -->': story.append(PageBreak()); continue
        if line.startswith('<!-- diagram:'):
            kind=line.split(':')[1].split()[0]
            story.append(Diagram(kind)); story.append(Spacer(1,4)); continue
        if line=='<!-- signatures -->':
            date=p('TP. HCM, ngày ...... tháng ...... năm ........','center')
            row=Table([[p('**Xác nhận của CBHD**<br>(Ký tên và ghi rõ họ tên)','center'),
                        p('**Sinh viên**<br>(Ký tên và ghi rõ họ tên)','center'),''],
                       [Spacer(1,44),Spacer(1,44),Spacer(1,44)],
                       [p('Nguyễn Thành Luân','center'),p('Phạm Quốc Thắng','center'),p('Lê Minh Thiện','center')]],colWidths=[WIDTH/3]*3)
            row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('SPAN',(1,0),(2,0))]))
            story.append(KeepTogether([Spacer(1,5),date,Spacer(1,5),row])); continue
        if line.startswith('|'):
            tablelines=[line]
            while index<len(lines) and lines[index].strip().startswith('|'):
                tablelines.append(lines[index].strip()); index+=1
            rows=[]
            for n,text in enumerate(tablelines):
                if n==1 and re.fullmatch(r'[| :\-]+',text): continue
                cells=[cell.strip() for cell in text.strip('|').split('|')]
                if cells[0].startswith('Tuần '):
                    cells[0] = cells[0].replace('–', '<br>– ')
                rows.append([p('**'+c+'**' if n==0 else c,'cell') for c in cells])
            first=tablelines[0]
            if 'Thời gian' in first: widths=[79,258,WIDTH-337]
            elif len(rows[0])==2: widths=[WIDTH*.31,WIDTH*.69]
            elif 'Cấu hình' in first: widths=[70,230,WIDTH-300]
            else: widths=[110,255,WIDTH-365]
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([
                ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#68737d')),
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf0f3')),
                ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ]))
            story.extend([table,Spacer(1,9)]); continue
        if line.startswith('### '): story.append(p(line[4:],'h3'))
        elif line.startswith('## '): story.append(p(line[3:],'h2'))
        elif line.startswith('# '): story.append(p(line[2:],'h1'))
        elif line.startswith('- '): story.append(p('• '+line[2:],'bullet'))
        elif line.startswith('*Hình'): story.append(p(line,'caption'))
        else: story.append(p(line))
    def footer(canvas,document):
        canvas.saveState(); canvas.setFont('Body',9); canvas.setFillColor(colors.HexColor('#56616b'))
        canvas.drawString(50,28,'Đề cương Việt–Tày • Bản cập nhật 01/11/2026')
        canvas.drawRightString(A4[0]-50,28,f'Trang {document.page}')
        canvas.restoreState()
    output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=50,leftMargin=50,
                          topMargin=40,bottomMargin=46,title='Đề cương đồ án tốt nghiệp Việt–Tày',
                          author='Phạm Quốc Thắng; Lê Minh Thiện')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'docs/DeCuongDATN_25410304_25410313.md')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--font-dir',type=Path,default=Path('/usr/share/fonts/truetype/freefont'))
    parser.add_argument('--overwrite',action='store_true')
    args=parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error('Đầu ra đã tồn tại; chọn file khác hoặc dùng --overwrite')
    build(args.source,args.output,args.font_dir)
    print(args.output)


if __name__=='__main__': main()
