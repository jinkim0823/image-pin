# SPDX-License-Identifier: GPL-3.0-only
"""Small English/Korean catalog, independent of the Qt runtime."""
import os

_language = 'system'
KOREAN = {
    'Copy': '복사',
    'Save Image…': '이미지 저장…',
    'Original Size': '원본 크기',
    'Lock Position and Size': '위치·크기 잠금',
    'Opacity': '투명도',
    'Close': '닫기',
    'Close All Pins': '모두 닫기',
    'Choose an Image': '고정할 이미지 선택',
    'Scroll to zoom · Shift: fine zoom · Alt: opacity': '휠: 확대·축소 · Shift: 미세 조절 · Alt: 투명도',
    'Could not save the image.': '이미지를 저장하지 못했어요.',
    'No image found. Copy an image or choose an image file.': '이미지가 없어요. 이미지를 복사하거나 이미지 파일을 선택해 주세요.',
    'Could not start GNOME Screenshot. Install gnome-screenshot and try again.': 'GNOME 캡처를 실행할 수 없어요. gnome-screenshot 설치를 확인해 주세요.',
    'Capture failed: {detail}': '캡처 실패: {detail}',
}


def set_language(language):
    global _language
    if language not in {'system', 'en', 'ko'}:
        raise ValueError('Language must be system, en or ko')
    _language = language


def current_language():
    if _language != 'system':
        return _language
    value = os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG', 'en')
    return 'ko' if value.lower().startswith('ko') else 'en'


def tr(message, **values):
    return (KOREAN.get(message, message) if current_language() == 'ko' else message).format(**values)
