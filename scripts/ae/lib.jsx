// 組み立ての部品。tr / eff / keys / rgb / ST（style.json の中身）は本体で定義済みのものを使う。
// 黒基調・差し色 ST.accent。字幕は下の黒帯の中に白文字（箱なし）。名前は「差し色の四角＋英字の肩書＋名前＋細い線」。

function cText(c, s, font, size, color, pos, track, just, name) {
  var l = c.layers.addText(s); var q = l.property('ADBE Text Properties').property('ADBE Text Document'); var d = q.value;
  d.font = font; d.fontSize = size; d.applyFill = true; d.fillColor = rgb(color); d.applyStroke = false; d.tracking = track || 0;
  d.justification = just || ParagraphJustification.LEFT_JUSTIFY; q.setValue(d);
  tr(l, 'ADBE Position').setValue(pos); if (name) l.name = name; return l;
}
function cShadow(l, op, dist, soft) { var ds = eff(l, 'ADBE Drop Shadow'); ds.property(1).setValue([0, 0, 0, 1]); ds.property(2).setValue(op); ds.property(3).setValue(135); ds.property(4).setValue(dist); ds.property(5).setValue(soft); return ds; }
function cRect(c, name, w, h, color, pos, anchor) {
  var l = c.layers.addShape(); l.name = name;
  var vg = l.property('ADBE Root Vectors Group').addProperty('ADBE Vector Group').property('ADBE Vectors Group');
  var rc = vg.addProperty('ADBE Vector Shape - Rect'); rc.property('ADBE Vector Rect Size').setValue([w, h]); rc.property('ADBE Vector Rect Position').setValue([w / 2, h / 2]);
  vg.addProperty('ADBE Vector Graphic - Fill').property('ADBE Vector Fill Color').setValue(rgb(color));
  tr(l, 'ADBE Anchor Point').setValue(anchor || [0, 0]); tr(l, 'ADBE Position').setValue(pos); return l;
}
// ぼけから定まって少し上がる（文字の登場）。t1 で短く消える
function cRise(l, t0, t1, dy) {
  dy = dy == null ? 18 : dy;
  var p = tr(l, 'ADBE Position').value;
  keys(tr(l, 'ADBE Position'), [[t0, [p[0], p[1] + dy]], [t0 + .55, p]], 5, 92);
  keys(tr(l, 'ADBE Opacity'), [[t0, 0], [t0 + .3, 100], [t1 - .22, 100], [t1, 0]], 30, 60);
  var b = eff(l, 'ADBE Gaussian Blur 2'); keys(b.property(1), [[t0, 14], [t0 + .45, 0]], 10, 85); try { b.property(3).setValue(1); } catch (e) {}
  l.inPoint = t0; l.outPoint = t1;
}
// 字幕：黒帯があれば下の帯の中、無ければ画面の下に白文字＋影
function cCaption(c, s, t0, t1, name) {
  var y = ST.letterbox ? 1025 : 990;
  var l = cText(c, s, ST.font_caption, ST.caption_size, '#ffffff', [960, y], 70, ParagraphJustification.CENTER_JUSTIFY, name);
  if (!ST.letterbox) cShadow(l, 190, 2, 16);
  l.inPoint = t0; l.outPoint = t1;
  keys(tr(l, 'ADBE Opacity'), [[t0, 0], [t0 + .14, 100], [t1 - .14, 100], [t1, 0]], 40, 40);
  var r = l.sourceRectAtTime(t0 + .2, false); if (r.width > 1700) tr(l, 'ADBE Scale').setValue([1700 / r.width * 100, 1700 / r.width * 100]);
  return l;
}
function cName(c, nm, role, x, y, t0, t1, name) {
  var sq = cRect(c, name + '_四角', 12, 12, ST.accent, [x, y - 13], [0, 0]);
  var nl = cText(c, nm, ST.font_name, 58, '#ffffff', [x, y + 74], 80, ParagraphJustification.LEFT_JUSTIFY, name + '_名前'); cShadow(nl, 150, 2, 24);
  var ln = cRect(c, name + '_線', 340, 2, '#ffffff', [x, y + 100], [0, 1]);
  var all = [sq, nl, ln];
  if (role) all.splice(1, 0, cText(c, role, ST.font_role, 20, ST.accent, [x + 26, y], 300, ParagraphJustification.LEFT_JUSTIFY, name + '_肩書'));   // 肩書が空なら出さない
  for (var i = 0; i < all.length; i++) cRise(all[i], t0 + i * .08, t1, 14);
  keys(tr(ln, 'ADBE Scale'), [[t0 + .24, [0, 100]], [t0 + .85, [100, 100]]], 5, 92);
  return all;
}
// 寄った後も絵が画面全体を覆うよう、中心（元画像の座標）を制限する
function clampAnchor(fc, s, rotDeg) {
  var m = 960 * Math.abs(Math.sin(rotDeg * Math.PI / 180)) + 10;
  var x0 = 960 / s + m, x1 = 1920 - 960 / s - m, y0 = 540 / s + m, y1 = 1080 - 540 / s - m;
  return [Math.max(x0, Math.min(x1, fc[0])), Math.max(y0, Math.min(y1, fc[1]))];
}
// 強調の瞬間に話者の顔へ素早く寄る（モーションブラー＋放射ブラー）
function punchTo(L, t, a0, s0, fc, s1, rot, dur, hold) {
  dur = dur || .2; rot = rot || 0;
  var a1 = clampAnchor(fc, s1 / 100, rot);
  L.motionBlur = true;
  keys(tr(L, 'ADBE Anchor Point'), [[t, a0], [t + dur, a1]], 5, 92);
  var sc = [[t, [s0, s0]], [t + dur, [s1, s1]]];
  if (hold) sc.push([t + dur + hold, [s1 * 1.03, s1 * 1.03]]);
  keys(tr(L, 'ADBE Scale'), sc, 5, 92);
  if (rot) keys(tr(L, 'ADBE Rotate Z'), [[t, 0], [t + dur, rot]], 5, 92);
  try { var rb = eff(L, 'CC Radial Fast Blur'); keys(rb.property(2), [[t - .02, 0], [t + dur * .4, 38], [t + dur * 1.3, 0]], 30, 60); } catch (e) {}
  return a1;
}
