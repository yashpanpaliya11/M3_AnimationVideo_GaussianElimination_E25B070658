"""Editable, original math animation. Python 3.10+, Pillow, numpy, reportlab; ffmpeg.
macOS `say` creates narration. Else supply numbered WAV files in --work/audio.
Run: uv run --with pillow --with numpy --with reportlab python render_video.py
"""
import argparse, json, math, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SCENES = json.loads((Path(__file__).parent / 'scenes.json').read_text())
W, H, FPS = 1920, 1080, 24
BG = '#f3ead7'
PANEL = '#fffefa'
LINE = '#c9beaa'
INK = '#171612'
MUTED = '#554f44'
ACTIVE = '#171612'
ACCENT = '#39352d'
HIGHLIGHT = '#e9d8b5'
PLANE_GRAY = '#605c55'
CONTRAST = '#171612'
FONTROOT=Path('/System/Library/Fonts/Supplemental')
FONTS={}
def font(n, bold=False, mono=False):
    key=(n,bold,mono)
    if key not in FONTS:
        filename='Courier New.ttf' if mono else ('Arial Bold.ttf' if bold else 'Arial.ttf')
        p=FONTROOT/filename
        if not p.exists():
            p=Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSansMono.ttf' if mono else 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
        FONTS[key]=ImageFont.truetype(str(p),n)
    return FONTS[key]
def text(d,xy,s,n=36,c=INK,bold=False,anchor=None,mono=False):
    d.text(xy,str(s),font=font(n,bold,mono),fill=c,anchor=anchor)
def wrap(d,s,x,y,width,n=33,c=MUTED,gap=12,bold=False):
    if '\n' in s:
        for line in s.splitlines():
            y = wrap(d, line, x, y, width, n, c, gap, bold)
        return y
    line=''
    for word in s.split():
        test=(line+' '+word).strip()
        if d.textlength(test,font=font(n,bold))>width and line:
            text(d,(x,y),line,n,c,bold); y+=n+gap; line=word
        else: line=test
    if line: text(d,(x,y),line,n,c,bold)
    return y+n+gap
def box(d,xy,fill=PANEL,outline=LINE,r=24):
    d.rounded_rectangle(xy,radius=r,fill=fill,outline=outline,width=2)
def ease(x):
    x=max(0,min(1,x)); return x*x*(3-2*x)
def arrow(d,a,b,c=ACTIVE,width=5):
    d.line([a,b],fill=c,width=width)
    ang=math.atan2(b[1]-a[1],b[0]-a[0])
    pts=[b,(b[0]-18*math.cos(ang-.5),b[1]-18*math.sin(ang-.5)),(b[0]-18*math.cos(ang+.5),b[1]-18*math.sin(ang+.5))]
    d.polygon(pts,fill=c)

M0=[[1,1,1,6],[2,3,1,11],[3,2,5,22]]
M1=[[1,1,1,6],[0,1,-1,-1],[3,2,5,22]]
M2=[[1,1,1,6],[0,1,-1,-1],[0,-1,2,4]]
M3=[[1,1,1,6],[0,1,-1,-1],[0,0,1,3]]

COLUMN_X = [300, 460, 620, 835]
ROW_Y = [427, 562, 697]
COLUMN_CUES = (.25, .39, .53, .67)

def row_updates(progress):
    return [ease((progress - cue) / .042) for cue in COLUMN_CUES]

def matrix(d, mat, pivots=(), target=None, progress=1, old=None, source=None):
    box(d, (130, 295, 975, 805))
    updates = row_updates(progress) if old is not None else [1] * 4
    current = max((i for i, cue in enumerate(COLUMN_CUES) if progress >= cue - .03), default=-1)
    for x, label in zip(COLUMN_X, ['x', 'y', 'z', 'b']):
        text(d, (x, 341), label, 32, MUTED, True, anchor='mm')
    d.line([(725, 380), (725, 754)], fill=LINE, width=4)
    for r, y in enumerate(ROW_Y):
        if r == target:
            box(d, (231, y-52, 903, y+52), HIGHLIGHT, INK, 16)
        elif r == source:
            box(d, (231, y-52, 903, y+52), PANEL, LINE, 16)
        text(d, (169, y), f'R{r+1}', 28, INK if r == target else MUTED, r == target, anchor='mm')
        for c, x in enumerate(COLUMN_X):
            val = mat[r][c]
            if (r,c) in pivots:
                d.rounded_rectangle((x-43,y-43,x+43,y+43), radius=18, fill=INK)
                text(d, (x,y), val, 62, PANEL, True, anchor='mm')
                continue
            if r == target and old is not None:
                q = updates[c]
                if c == current and progress < .81:
                    d.rounded_rectangle((x-46,y-43,x+46,y+43),radius=13,fill=INK)
                    color = PANEL
                else:
                    color = INK
                # Show a single number per cell during the roll.
                val = old[r][c] if q < .5 else val
                shift = -20*q if q < .5 else 20*(1-q)
                text(d, (x,y+shift), str(val).replace('-', '−'), 61, color, True, anchor='mm')
            else:
                if r == source and c == current and progress < .81:
                    d.rounded_rectangle((x-46,y-43,x+46,y+43),radius=13,outline=INK,width=3)
                text(d, (x,y), str(val).replace('-', '−'), 61, INK, True, anchor='mm')
    for x, sign in [(217,1),(930,-1)]:
        d.line([(x+sign*18,380),(x,380),(x,751),(x+sign*18,751)],fill=INK,width=4)

def equations(d,lines,active=None,x=1140,y=400,n=48):
    for i,line in enumerate(lines):
        text(d,(x,y+i*110),line,n,ACTIVE if i==active else INK,True)

def planes(im,u):
    # Three exact plane patches centred at the common point (1,2,3).
    # R2(t)=R2-2t R1 is reversible; common point remains fixed.
    d=ImageDraw.Draw(im); theta=-.70+.16*math.sin(u*math.pi*2)
    def project(v):
        x,y,z=np.array(v)-np.array([1,2,3]); a=math.cos(theta)*x-math.sin(theta)*y
        b=math.sin(theta)*x+math.cos(theta)*y
        return (600+115*a,590-90*z+42*b)
    origin = (210, 758)
    for offset,label in [((127,-52),'x'),((100,54),'y'),((0,-132),'z')]:
        tip = (origin[0]+offset[0], origin[1]+offset[1])
        arrow(d,origin,tip,MUTED,3)
        text(d,(tip[0]+12,tip[1]-8),label,27,MUTED)
    k=ease((u-.20)/.5)
    defs=[(1,1,1,6,PLANE_GRAY),(2-2*k,3-2*k,1-2*k,11-12*k,ACTIVE),(3,2,5,22,ACCENT)]
    overlay=Image.new('RGBA',im.size); od=ImageDraw.Draw(overlay)
    for a,b,c,v,color in defs:
        pts=[]
        for dx,dz in [(-2,-1.2),(2,-1.2),(2,1.2),(-2,1.2)]:
            x=1+dx; z=3+dz; y=(v-a*x-c*z)/b; pts.append(project([x,y,z]))
        rgb=tuple(int(color[i:i+2],16) for i in [1,3,5])
        od.polygon(pts,fill=rgb+(55,),outline=rgb+(230,),width=3)
    im.alpha_composite(overlay); d=ImageDraw.Draw(im)
    p=project([1,2,3]); d.ellipse((p[0]-10,p[1]-10,p[0]+10,p[1]+10),fill=INK)
    text(d,(p[0]+18,p[1]+8),'same intersection',26,INK)

CHAPTERS=['Hook & context','The concept','Visual intuition','Worked example','Interpretation','Summary & credits']
def frame(i,t,duration):
    s=SCENES[i]; u=t/duration; k=s['kind']; im=Image.new('RGBA',(W,H),BG); d=ImageDraw.Draw(im)
    text(d,(100,52),'M3  /  LINEAR ALGEBRA',25,INK,True)
    text(d,(1820,52),CHAPTERS[s['chapter']-1].upper(),24,MUTED,True,anchor='ra')
    d.line((100,108,1820,108),fill=LINE,width=2)
    if k != 'intro':
        text(d,(100,151),s['title'],66,INK,True)
    if k=='intro':
        text(d,(100,255),'Gaussian',142,INK,True)
        text(d,(100,393),'elimination',142,INK,True)
        text(d,(106,576),'Solving a 3 × 3 system',54,INK)
        text(d,(108,733),'Yash Panpaliya  ·  E25B070658',36,MUTED,True)
        box(d,(1090,230,1820,837),INK,INK,35)
        text(d,(1155,281),'FORWARD ELIMINATION',26,PANEL,True)
        stage = sum(u >= cue for cue in (.30,.47,.64))
        stage_matrix = (M0,M1,M2,M3)[stage]
        for row in range(3):
            for col in range(3):
                x=1282+col*172; y=392+row*135
                shift=28*(1-ease((t-.10*(row*3+col))/0.9))
                y += shift
                is_pivot = row == col and (row == 0 or stage >= row+1)
                fill = HIGHLIGHT if is_pivot else PANEL
                box(d,(x-65,y-48,x+65,y+48),fill,fill,15)
                val = stage_matrix[row][col]
                text(d,(x,y),str(val).replace('-','−'),57,INK,True,anchor='mm')
        text(d,(1455,768),'Create zeros below the pivots',30,PANEL,anchor='mm')
    elif k=='equations':
        box(d,(110,310,1110,815))
        for j,(eq,cue) in enumerate(zip(['x + y + z = 6','2x + 3y + z = 11','3x + 2y + 5z = 22'],(.11,.26,.47))):
            if u >= cue:
                y = 384+j*125
                shift = 20*(1-ease((u-cue)/.045))
                text(d,(165,y+13+shift),f'R{j+1}',28,MUTED,True)
                text(d,(282,y+shift),eq,61,INK,True)
        text(d,(1220,380),'ONE SHARED',38,ACTIVE,True); text(d,(1220,435),'SOLUTION',56,INK,True)
        wrap(d,'Find x, y and z that satisfy every equation.',1220,550,510,37)
    elif k=='planes':
        planes(im,u); d=ImageDraw.Draw(im)
        text(d,(1110,345),'One equation → one plane',36,PLANE_GRAY,True)
        text(d,(1110,425),'Three constraints → one point',36,INK,True)
        wrap(d,'A reversible row operation changes a plane while preserving the common intersection.',1110,535,670,34)
        text(d,(1110,735),'R2(t) = R2 − 2t R1',39,ACTIVE,True)
        text(d,(1110,800),'t goes from 0 to 1',27,MUTED)
    elif k=='rules':
        rules=[('01','SWAP','R1 ↔ R2'),('02','SCALE','R1 ← kR1   (k ≠ 0)'),('03','REPLACE','R2 ← R2 + kR1')]
        for j,(num,label,eq) in enumerate(rules):
            x=110+j*580; y=330; on=u>=j*.22
            box(d,(x,y,x+545,y+330),PANEL,ACTIVE if on else LINE)
            text(d,(x+35,y+35),num,30,ACTIVE); text(d,(x+35,y+100),label,37,INK,True)
            text(d,(x+35,y+210),eq,34,ACCENT)
        text(d,(140,745),'R2 − 2R1',46,ACTIVE,True); arrow(d,(540,770),(1210,770),ACCENT)
        text(d,(640,708),'undo with +2R1',32,MUTED); text(d,(1300,745),'original R2',46,INK,True)
    elif k in ['matrix_intro','pivot1','pivot2','op1','op2','op3','echelon','unique']:
        mats={'matrix_intro':M0,'pivot1':M0,'op1':M1,'op2':M2,'pivot2':M2,'op3':M3,'echelon':M3,'unique':M3}
        piv={'pivot1':[(0,0)],'op1':[(0,0)],'op2':[(0,0)],'pivot2':[(0,0),(1,1)],'op3':[(0,0),(1,1)],'echelon':[(0,0),(1,1),(2,2)],'unique':[(0,0),(1,1),(2,2)]}
        ops={'op1':(1,M0,'R2 ← R2 − 2R1',['2 − 2(1) = 0','3 − 2(1) = 1','1 − 2(1) = −1','11 − 2(6) = −1']),
             'op2':(2,M1,'R3 ← R3 − 3R1',['3 − 3(1) = 0','2 − 3(1) = −1','5 − 3(1) = 2','22 − 3(6) = 4']),
             'op3':(2,M2,'R3 ← R3 + R2',['0 + 0 = 0','−1 + 1 = 0','2 + (−1) = 1','4 + (−1) = 3'])}
        op = ops.get(k)
        source = (1 if k == 'op3' else 0) if op else None
        matrix(d, mats[k], piv.get(k,()), op[0] if op else None, u, op[1] if op else None, source)
        if op:
            box(d,(1035,295,1810,805))
            text(d,(1090,327),op[2],54,INK,True)
            for j,(label,line,cue) in enumerate(zip(('x','y','z','b'),op[3],COLUMN_CUES)):
                y=430+j*82
                if u >= cue-.03:
                    active = u < (COLUMN_CUES[j+1]-.03 if j < 3 else .81)
                    shift = 16*(1-ease((u-cue+.03)/.035))
                    if active:
                        box(d,(1071,y-12,1770,y+59),INK,INK,13)
                    text(d,(1100,y+shift),label,36,PANEL if active else MUTED,True)
                    text(d,(1200,y-4+shift),line,43,PANEL if active else INK,True)
            text(d,(1070,831),'Use the same operation on all four columns.',29,MUTED)
        elif k=='matrix_intro':
            text(d,(1080,360),'[ A | b ]',75,ACTIVE,True)
            wrap(d,'A = coefficient matrix\nb = constants\nEach row = one equation',1080,490,660,35)
            text(d,(1080,715),'Column order: x, y, z',36,ACCENT)
        elif k=='pivot1':
            text(d,(1080,370),'PIVOT 1',44,ACCENT,True)
            wrap(d,'Use the leading 1 to cancel the 2 and 3 below it.',1080,465,650,40)
            arrow(d,(380,480),(380,650),ACCENT)
            text(d,(1080,705),'Goal: remove x from R2 and R3',31,ACTIVE)
        elif k=='pivot2':
            text(d,(1080,365),'PIVOT 2',44,ACCENT,True)
            wrap(d,'Use the second pivot to eliminate the −1 below it.',1080,460,650,40)
            arrow(d,(540,610),(540,670),ACCENT)
            text(d,(1080,715),'−1 + 1 = 0',51,ACTIVE,True)
        elif k=='echelon':
            equations(d,['x + y + z = 6','y − z = −1','z = 3'],None,1070,410,48)
            text(d,(1070,780),'Now solve from bottom to top.',31,ACTIVE)
        elif k=='unique':
            text(d,(1090,360),'3 pivots',65,ACCENT,True)
            text(d,(1090,460),'3 unknowns',65,INK,True)
            text(d,(1090,595),'0 free variables',46,ACTIVE,True)
            text(d,(1090,710),'Exactly one solution.',39,INK)
    elif k in ['backz','backy','backx']:
        active={'backz':2,'backy':1,'backx':0}[k]
        box(d,(110,325,890,815))
        lines=['x + y + z = 6','y − z = −1','z = 3']
        for j,line in enumerate(lines):
            y = 405+j*122
            if j == active:
                box(d,(147,y-12,842,y+71),HIGHLIGHT,LINE,14)
            text(d,(185,y),line,52,INK,j==active)
        if k in ['backy','backx']:
            # The known values move from their rows to the active equation.
            chips = [('3',2)] if k=='backy' else [('2',1),('3',2)]
            for j,(value, from_row) in enumerate(chips):
                amount=ease((u-.22-j*.045)/.18)
                x=760 + j*67
                start_y = 432+from_row*122
                end_y = 432+active*122
                y = start_y + (end_y-start_y)*amount
                d.ellipse((x-25,y-25,x+25,y+25),fill=INK)
                text(d,(x,y),value,32,PANEL,True,anchor='mm')
        steps={
            'backz': [('Read the last row','1z = 3',.06),('Solve for z','z = 3',.25)],
            'backy': [('Substitute z = 3','y − 3 = −1',.41),('Add 3 to both sides','y = 2',.63)],
            'backx': [('Substitute y = 2 and z = 3','x + 2 + 3 = 6',.43),('Subtract 5 from both sides','x = 1',.63)],
        }[k]
        for j,(label,eq,cue) in enumerate(steps):
            y = 340+j*232
            if u < cue:
                continue
            shift = 24*(1-ease((u-cue)/.045))
            fill, ink = (INK,PANEL) if j==1 else (PANEL,INK)
            box(d,(1010,y+shift,1810,y+shift+193),fill,LINE,21)
            text(d,(1065,y+27+shift),label,33,ink)
            text(d,(1065,y+79+shift),eq,63,ink,True)
    elif k=='verify':
        checks=[('x + y + z','1 + 2 + 3 = 6'),('2x + 3y + z','2 + 6 + 3 = 11'),('3x + 2y + 5z','3 + 4 + 15 = 22')]
        for j,(label,eq) in enumerate(checks):
            y=330+j*155; box(d,(110,y,1810,y+130)); text(d,(150,y+40),label,39,MUTED)
            if u>.10+j*.22: text(d,(740,y+35),eq,49,INK,True); text(d,(1660,y+41),'PASS',30,ACTIVE,True)
        if u > .68:
            text(d,(125,840),'(x, y, z) = (1, 2, 3)',45,ACTIVE,True)
    elif k=='cases':
        items=[('NO SOLUTION','[ 0  0  0 | 5 ]','0 = 5: a contradiction.',CONTRAST),('INFINITELY MANY','[ 0  0  0 | 0 ]','Consistent + a free variable.',ACTIVE)]
        for j,(label,eq,desc,color) in enumerate(items):
            x=110+j*870; box(d,(x,335,x+830,775)); text(d,(x+40,375),label,35,color,True)
            text(d,(x+40,485),eq,48,INK,mono=True); wrap(d,desc,x+40,615,740,37)
        text(d,(130,830),'A zero row alone does not establish the number of solutions.',31,ACCENT)
    elif k=='summary':
        for j,(num,title,desc) in enumerate([('1','Preserve','Use reversible row operations.'),('2','Eliminate','Create zeros below each pivot.'),('3','Substitute','Solve upward: z, then y, then x.')]):
            y=335+j*165; box(d,(110,y,1805,y+140)); text(d,(150,y+27),num,64,ACTIVE,True)
            text(d,(290,y+40),title,46,INK,True); text(d,(750,y+47),desc,35,MUTED)
        text(d,(125,865),'Solution: x = 1, y = 2, z = 3',39,ACCENT,True)
    elif k=='quiz':
        box(d,(110,330,970,820)); text(d,(210,405),'[ 2   1 | 5 ]',60,INK,mono=True)
        text(d,(210,555),'[ 4   3 | 9 ]',60,INK,mono=True)
        text(d,(1070,385),'Which operation clears the 4?',36,INK,True)
        if u>.55:
            text(d,(1080,525),'R2 ← R2 − 2R1',49,ACTIVE,True)
            text(d,(1080,650),'Multiplier = 4 / 2 = 2',36,ACCENT)
        else: text(d,(1080,550),'Pause and try it.',49,ACCENT,True)
        text(d,(180,740),'Target entry / pivot',33,MUTED)
    elif k=='credits':
        text(d,(120,330),'Yash Panpaliya',57,INK,True); text(d,(120,410),'E25B070658',40,ACTIVE)
        text(d,(120,520),'SOURCES',25,ACCENT,True)
        wrap(d,'M3 Animation Video Project Instructions (course handout).\nOpenStax, College Algebra 2e, Section 7.6: Solving Systems with Gaussian Elimination.',120,570,810,30)
        text(d,(1090,330),'AI & PRODUCTION DISCLOSURE',26,ACCENT,True)
        wrap(d,'OpenAI Codex: script, example design, animation code and supporting documents. Apple Samantha synthetic English narration. Pillow + FFmpeg: original procedural animation. No music or stock visual assets.',1090,400,700,32)
        text(d,(120,815),'Source code and storyboard included.',31,MUTED)
    # Lesson caption: a consistent reading zone, never covers the mathematics.
    d=ImageDraw.Draw(im)
    d.rectangle((0,931,W,H),fill=INK)
    caption = s['caption']
    # Withhold answers while the viewer works through the animation.
    open_captions = {
        'backz': 'Find the row with just one unknown. Start there.',
        'backy': 'Carry z = 3 into the second equation.',
        'backx': 'Carry y = 2 and z = 3 into the first equation.',
        'quiz': 'Which operation clears the 4? Pause here to try it.',
    }
    if u < .67:
        caption = open_captions.get(k, caption)
    wrap(d,caption,100,962,1720,34,PANEL,8)
    d.rectangle((100,1044,1820,1047),fill='#656057')
    d.rectangle((100,1044,100+int(1720*u),1047),fill=HIGHLIGHT)
    return im.convert('RGB')

def run(cmd,**kw): return subprocess.run(cmd,check=True,**kw)
def duration(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)]))

def documents(out,times):
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import simpleSplit
    c=canvas.Canvas(str(out/'Storyboard.pdf'),pagesize=(595,842))
    descriptions=[('Hook / context','Introduce a tangled 3-equation system and the staircase metaphor.'),('Concept introduction','Define unknowns, constraints and a shared solution.'),('Visual intuition','Animate three planes; change one through a reversible row replacement. Define the three allowed operations.'),('Worked example','Build [A|b]. Highlight pivots. Animate every row operation entry by entry, including constants. Read echelon form and substitute upward.'),('Interpretation','Check all three original equations. Explain uniqueness and contrast inconsistent and underdetermined systems.'),('Summary & credits','Recap three ideas, offer a short practice question, and disclose sources and AI assistance.')]
    elapsed=0; starts=[]
    for sec in times: starts.append(elapsed); elapsed+=sec
    def stamp(t): return f'{int(t)//60:02}:{int(t)%60:02}'
    for ch,(title,desc) in enumerate(descriptions,1):
        c.setFillColor(HexColor(BG)); c.rect(0,0,595,842,fill=1,stroke=0)
        c.setFillColor(HexColor(ACTIVE)); c.setFont('Helvetica-Bold',11); c.drawString(42,792,'M3 ANIMATION VIDEO / SIX-SCENE STORYBOARD')
        c.setFillColor(HexColor(INK)); c.setFont('Helvetica-Bold',23); c.drawString(42,744,f'{ch:02}  {title}')
        c.setFont('Helvetica',11); c.setFillColor(HexColor(MUTED)); c.drawString(42,714,'Yash Panpaliya | E25B070658 | Gaussian elimination')
        y=665
        for line in simpleSplit(desc,'Helvetica',12,505): c.drawString(42,y,line); y-=19
        y-=20
        if ch==1:
            objective='Learning objective: explain and perform forward elimination on a 3 x 3 system, identify pivots, use back substitution, and verify the solution.'
            for line in simpleSplit(objective,'Helvetica',12,505): c.drawString(42,y,line); y-=19
            y-=20
        for i,s in enumerate(SCENES):
            if s['chapter']!=ch: continue
            c.setFillColor(HexColor(ACTIVE)); c.setFont('Helvetica-Bold',11)
            c.drawString(42,y,f'{stamp(starts[i])} - {stamp(starts[i]+times[i])}   {s["title"]}'); y-=21
            c.setFillColor(HexColor(INK)); c.setFont('Helvetica',10)
            # ASCII substitutions keep built-in PDF fonts reliable.
            line=s['caption'].replace('←','<-').replace('→','->').replace('−','-').replace('·',' / ')
            for q in simpleSplit(line,'Helvetica',10,505): c.drawString(42,y,q); y-=15
            y-=14
        c.setFillColor(HexColor(MUTED)); c.setFont('Helvetica',9)
        c.drawString(42,52,'Narration and complete shot descriptions: Narration_Transcript.txt and Code/scenes.json')
        c.drawRightString(550,30,f'{ch} / 6'); c.showPage()
    c.save()
    transcript=['GAUSSIAN ELIMINATION - ENGLISH NARRATION','Yash Panpaliya | E25B070658','']
    for i,s in enumerate(SCENES):
        transcript.extend([f'{stamp(starts[i])}  {s["title"]}',s['voice'],''])
    (out/'Narration_Transcript.txt').write_text('\n'.join(transcript))
    (out/'Timeline.json').write_text(json.dumps([dict(title=s['title'],start=starts[i],duration=times[i]) for i,s in enumerate(SCENES)],indent=2))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,default=ROOT/'render_work'); p.add_argument('--previews-only',action='store_true'); p.add_argument('--voice',default='Samantha'); p.add_argument('--rate',default='190'); args=p.parse_args()
    out=ROOT; work=args.work; work.mkdir(parents=True,exist_ok=True); (work/'audio').mkdir(exist_ok=True); (work/'previews').mkdir(exist_ok=True)
    # Exact row arithmetic and original-system check, independent of graphics.
    a=np.array(M0,dtype=int); b=a.copy(); b[1]-=2*b[0]; assert b.tolist()==M1
    b[2]-=3*b[0]; assert b.tolist()==M2
    b[2]+=b[1]; assert b.tolist()==M3
    assert np.array_equal(a[:,:3]@np.array([1,2,3]),a[:,3])
    assert round(np.linalg.det(a[:,:3]))==1
    times=[]
    for i,s in enumerate(SCENES):
        wav=work/'audio'/f'{i:02}.wav'; speech=work/'audio'/f'{i:02}.txt'; speech.write_text(s['voice'])
        if not wav.exists():
            aiff=wav.with_suffix('.aiff'); run(['say','-v',args.voice,'-r',args.rate,'-f',str(speech),'-o',str(aiff)])
            run(['ffmpeg','-v','error','-y','-i',str(aiff),'-ar','48000','-ac','1',str(wav)])
        times.append(math.ceil((duration(wav)+1.3)*FPS)/FPS)
    assert sum(times)<420, f'Too long: {sum(times):.1f}s; increase speech rate.'
    print(f'Voice ready. Total runtime: {sum(times):.2f}s.',flush=True)
    documents(out,times)
    thumbs=[]
    for i,sec in enumerate(times):
        im=frame(i,sec*.82,sec); im.save(work/'previews'/f'{i:02}.png'); im.thumbnail((480,270)); thumbs.append(im)
    contact=Image.new('RGB',(1920,1350),BG)
    for i,im in enumerate(thumbs): contact.paste(im,((i%4)*480,(i//4)*270))
    contact.save(work/'previews'/'contact_sheet.jpg')
    if args.previews_only: return
    segments=[]
    for i,sec in enumerate(times):
        target=work/f'segment_{i:02}.mp4'; segments.append(target)
        if target.exists(): continue
        print(f'Rendering {i+1}/{len(SCENES)}: {SCENES[i]["title"]} ({sec:.1f}s)',flush=True)
        cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-', '-i',str(work/'audio'/f'{i:02}.wav'),'-c:v','libx264','-preset','ultrafast','-crf','22','-threads','4','-pix_fmt','yuv420p','-af','adelay=400:all=1,apad','-c:a','aac','-b:a','128k','-t',str(sec),str(target)]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for n in range(round(sec*FPS)): proc.stdin.write(frame(i,n/FPS,sec).tobytes())
        finally: proc.stdin.close()
        assert proc.wait()==0,'ffmpeg failed'
    listing=work/'segments.txt'; listing.write_text('\n'.join("file '"+str(x.resolve()).replace("'","'\\''")+"'" for x in segments))
    chapters = work / 'chapters.ffmeta'
    metadata = [';FFMETADATA1']
    elapsed = 0.0
    for scene, seconds in zip(SCENES, times):
        start = round(elapsed * 1000)
        elapsed += seconds
        metadata.extend(['[CHAPTER]', 'TIMEBASE=1/1000',
                         f'START={start}', f'END={round(elapsed * 1000)}',
                         f'title={scene["title"]}'])
    chapters.write_text('\n'.join(metadata) + '\n')
    final = out / 'Gaussian_Elimination_Yash_Panpaliya.mp4'
    staged = final.with_suffix('.rendering.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing),
         '-f', 'ffmetadata', '-i', str(chapters), '-map', '0:v:0', '-map', '0:a:0',
         '-map_chapters', '1', '-c', 'copy', '-movflags', '+faststart', str(staged)])
    staged.replace(final)
    print(f'FINISHED: {final}',flush=True)

if __name__=='__main__': main()
