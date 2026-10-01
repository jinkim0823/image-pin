# SPDX-License-Identifier: GPL-3.0-only
"""Render a public preview from generated images only, using the actual overlay."""
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QImage, QWheelEvent, QPen
from image_pin import gui_types

Application, Manager, _ = gui_types()
app = Application([])
app.setQuitOnLastWindowClosed(False)
manager = Manager(serve=False)
manager.surface.setGeometry(0, 0, 900, 540)
assets = PROJECT / 'docs/assets'
assets.mkdir(parents=True, exist_ok=True)

card = QPixmap(420, 245)
card.fill(QColor('#172537'))
painter = QPainter(card)
painter.setRenderHint(QPainter.Antialiasing)
painter.setPen(QColor('#eef3ff'))
painter.setFont(QFont('sans', 17, QFont.Bold))
painter.drawText(24, 36, 'Reference curve')
painter.setPen(QPen(QColor('#34475b'), 1))
for x in range(35, 410, 35):
    painter.drawLine(x, 62, x, 215)
for y in range(65, 225, 30):
    painter.drawLine(25, y, 395, y)
painter.setPen(QPen(QColor('#ffba76'), 3))
for x in range(26, 395):
    y = 182 - 65 * math.sin((x-26) / 95)
    painter.drawLine(QPointF(x, y), QPointF(x+1, 182-65*math.sin((x+1-26)/95)))
painter.end()
pin = manager.pin(card)
pin.scale = .85
pin.center = QPointF(450, 300)
manager.changed()

# A 512px icon for the independent MIT launcher wrapper.
icon = QPixmap(512,512)
icon.fill(Qt.transparent)
p = QPainter(icon)
p.setRenderHint(QPainter.Antialiasing)
p.setPen(Qt.NoPen)
p.setBrush(QColor('#172537'))
p.drawRoundedRect(QRectF(0,0,512,512), 104,104)
p.setBrush(QColor('#426794'))
p.drawRoundedRect(QRectF(98,108,236,218), 25,25)
p.setBrush(QColor('#f2f5ff'))
p.drawRoundedRect(QRectF(163,173,251,230), 25,25)
p.setPen(QPen(QColor('#ef9862'),16,Qt.SolidLine,Qt.RoundCap))
p.drawLine(213,254,267,220)
p.drawLine(267,220,316,296)
p.drawLine(316,296,367,251)
p.end()
icon.save(str(PROJECT/'extension/assets/icon.png'))

# GIF timestamps use hundredths of a second: 50 fps has an exact 20ms
# interval. Avoid the original 20fps preview with isolated wheel clicks.
FPS = 50
DURATION = 7.
pointer = QPointF(500,300)
wheel_total = 0
holding = False

def smooth_step(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)

def scroll_to(total):
    global wheel_total
    target = round(total)
    delta = target - wheel_total
    if delta:
        wheel = QWheelEvent(pointer,pointer,QPoint(),QPoint(0,delta),
                            Qt.LeftButton if holding else Qt.NoButton,
                            Qt.NoModifier,Qt.NoScrollPhase,False)
        pin.wheelEvent(wheel)
    wheel_total = target

with tempfile.TemporaryDirectory(prefix='image-pin-demo-') as directory:
    frames = Path(directory)
    for index in range(round(FPS * DURATION)):
        time = index / FPS
        title = 'Zoom where you point'
        # Feed fine-grained wheel packets to the unmodified app. The smooth
        # trajectory belongs to scripted input, not to a fake UI animation.
        if time < 2.2:
            scroll_to(480 * smooth_step((time - .3) / 1.6))
        elif time < 4.1:
            title = 'Drag and zoom together'
            if not holding:
                pin.begin_drag(pointer)
                holding = True
            amount = smooth_step((time - 2.2) / 1.6)
            pointer = QPointF(500 + 65 * amount, 300 - 24 * amount)
            pin.drag(pointer)
            scroll_to(480 - 360 * amount)
        elif time < 5.2:
            title = 'Adjust opacity without changing the original'
            if holding:
                pin.end_drag()
                holding = False
            pin.set_opacity(1 - .35 * smooth_step((time - 4.1) / .7))
        else:
            title = 'Drag and zoom together' if time < 6.6 else 'Zoom where you point'
            if not holding:
                pin.begin_drag(pointer)
                holding = True
            amount = smooth_step((time - 5.2) / 1.3)
            pointer = QPointF(565 - 65 * amount, 276 + 24 * amount)
            pin.drag(pointer)
            scroll_to(120 * (1 - amount))
            pin.set_opacity(.65 + .35 * amount)
            if time >= 6.6:
                pin.end_drag()
                holding = False
        app.processEvents()
        frame = QImage(900,540,QImage.Format_ARGB32)
        frame.fill(QColor('#0c1420'))
        p = QPainter(frame)
        p.setPen(QColor('#f2f5ff'))
        p.setFont(QFont('sans',25,QFont.Bold)); p.drawText(38,53,'Image Pin')
        p.setFont(QFont('sans',14)); p.setPen(QColor('#a8b9cf')); p.drawText(38,85,title)
        p.setPen(Qt.NoPen); p.setBrush(QColor('#253248')); p.drawRoundedRect(QRectF(90,120,720,330),12,12)
        p.setPen(QColor('#a6bbd6')); p.setFont(QFont('monospace',12))
        for row,text in enumerate(['// Keep a reference above your work', '', 'const cursor = { x: 500, y: 300 };', 'const opacity = 0.65;', '', '// Transparent areas remain clickable']):
            p.drawText(115,163+row*36,text)
        p.drawPixmap(0,0,manager.surface.grab())
        p.setPen(QPen(QColor('#ffffff'),2)); p.setBrush(Qt.NoBrush); p.drawEllipse(pointer,6,6)
        p.setPen(QColor('#7e92ae')); p.setFont(QFont('sans',11)); p.drawText(38,505,'Rendered preview · scripted input · actual overlay renderer')
        p.end()
        frame.save(str(frames/f'{index:04d}.png'))
        if index == round(4.8 * FPS):
            frame.save(str(assets/'preview.png'))
    source = ['ffmpeg','-loglevel','error','-y','-framerate',str(FPS),
              '-i',str(frames/'%04d.png')]
    subprocess.run(source + ['-vf','split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse=dither=none',
                            str(assets/'demo.gif')], check=True)
    subprocess.run(source + ['-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
                            '-movflags','+faststart', str(assets/'demo.mp4')], check=True)
manager.close_all()
manager.surface.hide()
print('Rendered 50fps GIF, MP4 and preview.png using scripted input on the unchanged overlay')
