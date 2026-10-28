"""地図の場面（scenes.json の type: map）に使う輪郭と地点を作る → build/map.json {w, h, paths, places}
  pv.py map --places 東京=139.69,35.69 大阪=135.50,34.69 [--geojson <URL かファイル>]
既定の輪郭は日本の都道府県（dataofjapan/land の japan.geojson・出典：国土交通省 国土数値情報）。
ほかの国は Natural Earth などの GeoJSON を --geojson で渡す。データは同梱せず、そのつど取ってくる。"""
import json, math, urllib.request
from pathlib import Path

JAPAN = 'https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson'


def _rings(geom):
    t, c = geom['type'], geom['coordinates']
    if t == 'Polygon': return c
    if t == 'MultiPolygon': return [r for poly in c for r in poly]
    return []


def _simplify(pts, eps):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]; dx, dy = b[0] - a[0], b[1] - a[1]
        d = abs(dy * x - dx * y + b[0] * a[1] - b[1] * a[0]) / (math.hypot(dx, dy) or 1)
        if d > dmax: dmax, idx = d, i
    if dmax > eps: return _simplify(pts[:idx + 1], eps)[:-1] + _simplify(pts[idx:], eps)
    return [a, b]


def build(P, places, geojson=None, height=1000, eps=1.2, min_area=40):
    src = geojson or JAPAN
    data = json.loads(urllib.request.urlopen(src).read() if str(src).startswith('http') else Path(src).read_text())
    rings = [r for f in data['features'] for r in _rings(f['geometry'])]
    lon0 = min(p[0] for r in rings for p in r); lon1 = max(p[0] for r in rings for p in r)
    lat0 = min(p[1] for r in rings for p in r); lat1 = max(p[1] for r in rings for p in r)
    k = math.cos(math.radians((lat0 + lat1) / 2))
    sc = height / (lat1 - lat0); w = (lon1 - lon0) * k * sc
    proj = lambda lon, lat: ((lon - lon0) * k * sc, (lat1 - lat) * sc)
    paths = []
    for r in rings:
        pts = [proj(*p[:2]) for p in r]
        if len(pts) > 3 and pts[0] == pts[-1]:              # 閉じた輪郭は始点から一番遠い点で 2 つに分けて間引く（そのままだと 2 点につぶれる）
            far = max(range(len(pts)), key=lambda i: math.hypot(pts[i][0] - pts[0][0], pts[i][1] - pts[0][1]))
            pts = _simplify(pts[:far + 1], eps)[:-1] + _simplify(pts[far:], eps)
        else:
            pts = _simplify(pts, eps)
        if len(pts) < 3: continue
        area = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
        if area < min_area: continue
        paths.append('M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z')
    pl = {}
    for s in places:
        name, ll = s.split('=')
        lon, lat = map(float, ll.split(','))
        x, y = proj(lon, lat); pl[name] = [round(x, 1), round(y, 1)]
    P.jsave('map.json', dict(w=round(w, 1), h=height, paths=paths, places=pl, source=str(src)))
    print('map.json', len(paths), '本の輪郭', pl)
