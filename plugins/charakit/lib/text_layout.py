"""Measured, glyph-aware PNG captions with optional complex text shaping."""
from functools import lru_cache
from pathlib import Path
import unicodedata

from PIL import ImageFont, features
from fontTools.ttLib import TTFont


@lru_cache(maxsize=64)
def cmap(path):
    with TTFont(path, fontNumber=0, lazy=True) as font:
        return set(font.getBestCmap() or {})


def glyphs(text):
    return {ord(char) for char in text if not char.isspace() and unicodedata.category(char) not in ('Cc', 'Cf')
            and not 0xFE00 <= ord(char) <= 0xFE0F}


class TextPainter:
    def __init__(self, context, fallback):
        self.context = context
        self.fallback = fallback
        self.raqm = features.check_feature('raqm')
        self.loaded = {}
        self.paths = ([context.font_file] if context.font_file else []) + [
            'C:/Windows/Fonts/YuGothR.ttc', 'C:/Windows/Fonts/msgothic.ttc',
            'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/segoeui.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc']
        self.paths = [str(Path(p)) for p in self.paths if Path(p).is_file()]
        base = context.language.split('-')[0]
        if (context.direction == 'rtl' or base in ('hi', 'bn', 'ta', 'te', 'ml', 'kn', 'si', 'mr', 'ne', 'th', 'km', 'my')) and not self.raqm:
            raise context.locale.PresentationError('TEXT_LAYOUT_UNAVAILABLE', 'This language requires Pillow with libraqm text shaping.')

    def font(self, text, size):
        required = glyphs(text)
        for path in self.paths:
            if required <= cmap(path):
                key = (path, size)
                if key not in self.loaded:
                    self.loaded[key] = ImageFont.truetype(path, size)
                return self.loaded[key]
        candidate = self.fallback(size)
        path = getattr(candidate, 'path', None)
        if path and required <= cmap(str(path)):
            return candidate
        if self.context.strict or self.context.font_file or self.context.pack:
            raise self.context.locale.PresentationError('FONT_GLYPHS_MISSING', 'Provide --font-file covering the preview text: ' + text[:80])
        # Old projects keep their historical font behavior.
        return candidate

    def options(self):
        return {'direction': self.context.direction, 'language': self.context.language} if self.raqm else {}

    def width(self, text, size):
        return self.font(text, size).getlength(text, **self.options())

    def wrap(self, text, width, size):
        text = str(text)
        result = []
        for paragraph in text.splitlines() or ['']:
            clusters = []
            for char in paragraph:
                if clusters and (unicodedata.combining(char) or char in ('\u200d', '\ufe0f') or clusters[-1].endswith('\u200d')):
                    clusters[-1] += char
                else:
                    clusters.append(char)
            while clusters:
                count = 0
                while count < len(clusters) and self.width(''.join(clusters[:count+1]), size) <= width:
                    count += 1
                if count == 0:
                    raise self.context.locale.PresentationError('TEXT_LAYOUT_OVERFLOW', 'A text cluster exceeds the caption width.')
                if count < len(clusters):
                    spaces = [i for i in range(count) if clusters[i].isspace()]
                    if spaces:
                        count = spaces[-1] + 1
                result.append(''.join(clusters[:count]).rstrip())
                clusters = clusters[count:]
            if not paragraph:
                result.append('')
        return result

    def draw(self, draw, box, text, size, fill='#222222', spacing=5):
        x, y, width = box
        for line in self.wrap(text, width, size):
            font = self.font(line, size)
            at = x + width if self.context.direction == 'rtl' else x
            draw.text((at, y), line, font=font, fill=fill, anchor='rt' if self.context.direction == 'rtl' else 'lt', **self.options())
            y += size + spacing
        return y
