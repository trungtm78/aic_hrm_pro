# -*- coding: utf-8 -*-
"""Fold the customer document into one self-contained HTML file.

The document reads from `gioi-thieu-assets/`, which is fine on disk and
useless in an email: the customer gets one attachment, opens it, and every
screenshot is a broken icon. This inlines the images as data URIs so the file
travels alone.

Two judgement calls are worth stating.

The screenshots are captured at device scale 2 - 2880px wide - because that is
what makes them sharp on a retina display. Inlined at that size the file comes
out near 16MB, which most mail servers refuse. They are resized to 1600px,
which is still wider than the layout ever renders them (1080px), so nothing
visible is lost.

Quality is 82, not 60. This project has already had a round of "chữ mờ" on the
store listing; screenshots of dense UI text are exactly where aggressive JPEG
compression shows, and a smaller file nobody can read is not a smaller file.

    python tools/build_single_file_doc.py
    python tools/build_single_file_doc.py --width 1400 --quality 78
"""
import argparse
import base64
import io
import os
import re
import sys

from PIL import Image

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'Docs')
DEFAULT_SOURCE = os.path.join(DOCS, 'Gioi-thieu-he-thong-AIC-HRM-Pro.html')
DEFAULT_OUTPUT = os.path.join(DOCS, 'AIC-HRM-Pro-Huong-dan-su-dung.html')

IMG_RE = re.compile(r'src="([^"]+\.(?:png|jpg|jpeg|gif|svg))"', re.I)


def encode(path, max_width, quality):
    """Return a data URI, resized and re-encoded, plus the byte count."""
    with Image.open(path) as image:
        image = image.convert('RGB')
        if image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True,
                   progressive=True)
    payload = buffer.getvalue()
    return 'data:image/jpeg;base64,' + base64.b64encode(payload).decode(), len(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=DEFAULT_SOURCE)
    parser.add_argument('--output', default=DEFAULT_OUTPUT)
    parser.add_argument('--width', type=int, default=1600)
    parser.add_argument('--quality', type=int, default=82)
    args = parser.parse_args(argv)

    html = io.open(args.source, encoding='utf-8').read()
    base_dir = os.path.dirname(os.path.abspath(args.source))

    seen, missing, total = {}, [], 0

    def replace(match):
        nonlocal total
        src = match.group(1)
        if src.startswith('data:'):
            return match.group(0)
        path = os.path.normpath(os.path.join(base_dir, src))
        if not os.path.exists(path):
            missing.append(src)
            return match.group(0)
        if src not in seen:
            uri, size = encode(path, args.width, args.quality)
            seen[src] = uri
            total += size
            print('  %-52s %6.0f KB' % (os.path.basename(src), size / 1024))
        return 'src="%s"' % seen[src]

    print('inlining images:')
    html = IMG_RE.sub(replace, html)

    # A single file must not reach for anything else at all.
    outside = re.findall(r'(?:href|src)="((?!data:|#)[^"]+)"', html)
    outside = [u for u in outside if not u.startswith(('http://', 'https://',
                                                       'mailto:'))]

    io.open(args.output, 'w', encoding='utf-8', newline='\n').write(html)
    size = os.path.getsize(args.output)

    print('\n%-24s %s' % ('images inlined', len(seen)))
    print('%-24s %.1f MB' % ('image payload', total / 1024 / 1024))
    print('%-24s %.1f MB' % ('output file', size / 1024 / 1024))
    print('%-24s %s' % ('output', args.output))
    if missing:
        print('MISSING (left as-is):', missing)
    if outside:
        print('STILL POINTS OUTSIDE THE FILE:', outside[:5])
    return 1 if (missing or outside) else 0


if __name__ == '__main__':
    sys.exit(main())
