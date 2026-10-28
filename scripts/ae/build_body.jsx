// PV の組み立て本体。pv.py ae が先頭に「var D = {...};」（build/_comp.json＋保存先）を付けて build/_ae/build.jsx にする。
// 開いているのがこの案件の .aep か、空の名称未設定のときだけ作り直す。それ以外（他の作業中のプロジェクト）は何もしない。
(function () {
  var stage = 'start', proj, comp, inner, ST = D.style;
  function rgb(h) { return [parseInt(h.substr(1, 2), 16) / 255, parseInt(h.substr(3, 2), 16) / 255, parseInt(h.substr(5, 2), 16) / 255]; }
  function tr(l, m) { return l.property('ADBE Transform Group').property(m); }
  function eff(l, m) { return l.property('ADBE Effect Parade').addProperty(m); }
  function nE(q) { var t = q.propertyValueType; return t == PropertyValueType.ThreeD ? 3 : (t == PropertyValueType.TwoD ? 2 : 1); }
  function keys(q, arr, o, i) {
    for (var k = 0; k < arr.length; k++) q.setValueAtTime(arr[k][0], arr[k][1]);
    var n = nE(q);
    for (var k = 1; k <= q.numKeys; k++) { var a = [], b = []; for (var d = 0; d < n; d++) { a.push(new KeyframeEase(0, i || 75)); b.push(new KeyframeEase(0, o || 75)); } try { q.setTemporalEaseAtKey(k, a, b); } catch (x) {} }
  }
// @@LIB@@
  function bars(c, name, t0, t1, slide) {   // 上下の黒帯（2.39:1）
    var top = c.layers.addSolid([0, 0, 0], name + '_上', 1920, 1080, 1), bot = c.layers.addSolid([0, 0, 0], name + '_下', 1920, 1080, 1);
    tr(top, 'ADBE Anchor Point').setValue([960, 1080]); tr(top, 'ADBE Position').setValue([960, 138]);
    tr(bot, 'ADBE Anchor Point').setValue([960, 0]); tr(bot, 'ADBE Position').setValue([960, 941]);
    var L = [top, bot];
    for (var i = 0; i < 2; i++) { L[i].inPoint = t0; L[i].outPoint = t1; }
    if (slide) {
      keys(tr(top, 'ADBE Position'), [[t0, [960, 0]], [t0 + .45, [960, 138]]], 10, 88);
      keys(tr(bot, 'ADBE Position'), [[t0, [960, 1080]], [t0 + .45, [960, 941]]], 10, 88);
    }
  }
  try {
    stage = 'プロジェクトの確認';
    var cur = app.project;
    if (cur) {
      var nm = cur.file ? cur.file.displayName : '';
      var mine = nm == D.aep_name;
      var empty = !cur.file && cur.numItems == 0;
      if (!mine && !empty) { var f0 = new File(D.checks + '/BUSY.txt'); f0.open('w'); f0.writeln(nm || '名称未設定（作業中）'); f0.close(); return; }
      cur.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    }
    proj = app.newProject(); proj.save(new File(D.aep));
    var fSrc = proj.items.addFolder('素材'), fFx = proj.items.addFolder('場面と強調');
    var cache = {};
    function foot(path, folder) { if (cache[path]) return cache[path]; var f = proj.importFile(new ImportOptions(new File(path))); f.parentFolder = folder || fSrc; cache[path] = f; return f; }

    stage = '中身のコンポ（映像）';
    inner = proj.items.addComp('映像', 1920, 1080, 1, D.total, D.fps); inner.bgColor = [0, 0, 0]; inner.motionBlur = true; inner.shutterAngle = 180;
    var lays = {};
    for (var i = 0; i < D.items.length; i++) {
      var it = D.items[i];
      var L = inner.layers.add(foot(it.file)); L.name = it.key;
      L.startTime = it.t0 - it.off; L.inPoint = it.t0 - it.pre; L.outPoint = it.t1;
      tr(L, 'ADBE Anchor Point').setValue(it.anchor); tr(L, 'ADBE Position').setValue([960, 540]);
      var s = it.scale;
      if (it.sync && !it.punched && it.t1 - it.t0 > 2) keys(tr(L, 'ADBE Scale'), [[it.t0 - it.pre, [s, s]], [it.t1, [s * 1.03, s * 1.03]]], .1, .1);   // 話している顔はゆっくり 3% 寄る
      else tr(L, 'ADBE Scale').setValue([s, s]);
      if (it.fin > 0) keys(tr(L, 'ADBE Opacity'), [[it.t0 - it.pre, 0], [it.t0 - it.pre + it.fin, 100]], 40, 40);
      if (it.fout > 0) keys(tr(L, 'ADBE Opacity'), [[it.t1 - it.fout, 100], [it.t1, 0]], 40, 40);
      if (it.look == 'night') {   // 夜：色を落として青く沈める
        var tn = eff(L, 'ADBE Tint'); tn.property(2).setValue([.78, .86, 1]); tn.property(3).setValue(78);
        var bc = eff(L, 'ADBE Brightness & Contrast 2'); bc.property(1).setValue(-26); bc.property(2).setValue(10);
      }
      if (s > 130) eff(L, 'ADBE Sharpen').property(1).setValue(Math.round(6 + (s - 100) * .2));
      lays[i] = L;
    }
    stage = '強調の寄り';
    for (var pi = 0; pi < D.punches.length; pi++) { var P = D.punches[pi]; punchTo(lays[P.item], P.t, P.a0, P.s0, P.fc, P.s1, P.rot, P.dur, P.hold); }
    stage = '強調の間は少し暗く';
    for (var bi = 0; bi < D.bigs.length; bi++) {
      var B = D.bigs[bi]; var dk = inner.layers.addSolid([0, 0, 0], '暗く_' + B.k, 1920, 1080, 1);
      dk.inPoint = B.t - .1; dk.outPoint = B.end;
      keys(tr(dk, 'ADBE Opacity'), [[B.t - .1, 0], [B.t + .2, 30], [B.end - .2, 30], [B.end, 0]], 40, 40);
    }

    stage = '本編のコンポ';
    comp = proj.items.addComp(D.name, 1920, 1080, 1, D.total, D.fps); comp.bgColor = [0, 0, 0]; comp.motionBlur = true; comp.shutterAngle = 180;
    comp.layers.add(inner).name = '映像';
    if (ST.base && ST.base != '#000000') { var bs = comp.layers.addSolid(rgb(ST.base), '地の色', 1920, 1080, 1); bs.moveToEnd(); }   // 明るい見た目は間（何も無い所）も地の色に
    stage = 'AI などの完成素材';
    for (var ai = 0; ai < D.fx.length; ai++) {
      var A = D.fx[ai]; if (!A.ai || !new File(A.file).exists) continue;
      var al = comp.layers.add(foot(A.file, fFx)); al.name = 'AI_' + A.k; al.startTime = A.t0 - (A.src || 0); al.inPoint = A.t0; al.outPoint = A.t1;
      var bx = A.box || [0, 0, 1920, 1080];                       // 枠を覆う大きさ（はみ出しは枠の形で切る）・ゆっくり寄る・溶けて入る
      var sh = A.shift || [0, 0];                                 // shift：枠の中で絵をずらす（顔が黒帯で切れるとき下げる）
      var asc = Math.max(bx[2] / al.source.width, bx[3] / al.source.height) * 100; tr(al, 'ADBE Position').setValue([bx[0] + bx[2] / 2 + sh[0], bx[1] + bx[3] / 2 + sh[1]]);
      if (A.zoom && A.zoom[0] != A.zoom[1]) keys(tr(al, 'ADBE Scale'), [[A.t0, [asc * A.zoom[0], asc * A.zoom[0]]], [A.t1, [asc * A.zoom[1], asc * A.zoom[1]]]], 15, 15);
      else { var z = A.zoom ? A.zoom[0] : 1; tr(al, 'ADBE Scale').setValue([asc * z, asc * z]); }
      if (A.matte && new File(A.matte).exists) {                    // 文字の形に抜く：透明の場面のアルファで映像を切る
        var ml = comp.layers.add(foot(A.matte, fFx)); ml.name = '抜き_' + A.k; ml.startTime = A.t0; ml.inPoint = A.t0; ml.outPoint = A.t1;
        ml.moveBefore(al); al.setTrackMatte(ml, TrackMatteType.ALPHA); ml.enabled = false;
      } else if (A.box) {
        var mt = comp.layers.addSolid([1, 1, 1], '枠_' + A.k, bx[2], bx[3], 1); tr(mt, 'ADBE Position').setValue([bx[0] + bx[2] / 2, bx[1] + bx[3] / 2]);
        mt.inPoint = A.t0; mt.outPoint = A.t1; mt.moveBefore(al); al.setTrackMatte(mt, TrackMatteType.ALPHA); mt.enabled = false;
      }
      if (A.fade > 0) keys(tr(al, 'ADBE Opacity'), [[A.t0, 0], [A.t0 + A.fade, 100]], 40, 40);
      if (A.fout > 0) keys(tr(al, 'ADBE Opacity'), [[A.t1 - A.fout, 100], [A.t1, 0]], 40, 40);
    }
    if (ST.vignette > 0) {
      stage = '周辺を暗く';
      var vg = comp.layers.addSolid([0, 0, 0], '周辺を暗く', 1920, 1080, 1);
      var mk = vg.property('ADBE Mask Parade').addProperty('ADBE Mask Atom'); mk.inverted = true;
      var sh = new Shape(); sh.vertices = [[960, 40], [1900, 540], [960, 1040], [20, 540]];
      sh.inTangents = [[-520, 0], [0, -280], [520, 0], [0, 280]]; sh.outTangents = [[520, 0], [0, 280], [-520, 0], [0, -280]]; sh.closed = true;
      mk.property('ADBE Mask Shape').setValue(sh); mk.property('ADBE Mask Feather').setValue([420, 420]);
      tr(vg, 'ADBE Opacity').setValue(ST.vignette);
    }
    if (ST.letterbox) {
      stage = '黒帯'; bars(comp, '黒帯', 0, D.total, false);
      if (ST.letterbox_open) {                                    // 山場で黒帯を 0.8 秒で開いて全面に
        var bt = comp.layer('黒帯_上'), bb = comp.layer('黒帯_下'), o = ST.letterbox_open;
        keys(tr(bt, 'ADBE Position'), [[o, [960, 138]], [o + .8, [960, 0]]], 40, 80);
        keys(tr(bb, 'ADBE Position'), [[o, [960, 941]], [o + .8, [960, 1080]]], 40, 80);
      }
    }
    stage = '場面';
    for (var fi = 0; fi < D.fx.length; fi++) {
      var X = D.fx[fi]; if (X.ai || X.matte_only || !new File(X.file).exists) continue;
      var fl = comp.layers.add(foot(X.file, fFx)); fl.name = '場面_' + X.k; fl.startTime = X.t0; fl.inPoint = X.t0; fl.outPoint = X.t1;
      if (X.blend == 'screen') fl.blendingMode = BlendingMode.SCREEN; else if (X.blend == 'add') fl.blendingMode = BlendingMode.ADD;
      if (X.fout > 0) keys(tr(fl, 'ADBE Opacity'), [[X.t1 - X.fout, 100], [X.t1, 0]], 40, 40);
    }
    for (var xb = 0; xb < D.bars.length; xb++) bars(comp, '声の場面の黒帯' + (xb + 1), D.bars[xb].t0, D.bars[xb].t1, true);
    stage = '名前';
    for (var si = 0; si < D.names.length; si++) { var S = D.names[si]; cName(comp, S.name, S.role, ST.name_pos[0], ST.name_pos[1], S.t0, S.t1, '名前' + (si + 1)); }
    stage = '強調文字';
    for (var bj = 0; bj < D.bigs.length; bj++) {
      var G = D.bigs[bj]; if (!new File(G.file).exists) continue;
      var gl = comp.layers.add(foot(G.file, fFx)); gl.name = '強調_' + G.k; gl.startTime = G.t; gl.inPoint = G.t; gl.outPoint = G.end;
    }
    stage = '字幕';
    for (var ci = 0; ci < D.subs.length; ci++) { var C = D.subs[ci]; cCaption(comp, C.text, C.t0, C.t1, '字幕' + (ci + 1)); }
    if (D.fx.length) { var lastFx = D.fx[D.fx.length - 1]; if (lastFx.t1 >= D.total - .5) { var tail = comp.layers.addSolid([0, 0, 0], '最後の黒', 1920, 1080, 1); tail.inPoint = lastFx.t1 - .04; } }
    if (ST.edge_fade > 0) {                                        // 頭と終わりを黒から／黒へ溶かす（式場の前後の黒につなぐ）
      var ef = comp.layers.addSolid([0, 0, 0], '頭と終わりの黒', 1920, 1080, 1);
      keys(tr(ef, 'ADBE Opacity'), [[0, 100], [ST.edge_fade, 0], [D.total - .2 - ST.edge_fade, 0], [D.total - .2, 100]], 40, 40);
    }
    stage = '音';
    if (new File(D.audio).exists) comp.layers.add(foot(D.audio)).name = '音（声・音楽・効果音を混ぜ済み）';
    stage = '保存';
    proj.save(new File(D.aep));
    stage = '確認用のコマ';
    for (var k = 0; k < D.checktimes.length; k++) comp.saveFrameToPng(D.checktimes[k], new File(D.checks + '/f_' + ('00000' + Math.round(D.checktimes[k] * 100)).slice(-6) + '.png'));
    var ok = new File(D.checks + '/DONE.txt'); ok.open('w'); ok.writeln(D.checktimes.length); ok.close();
  } catch (err) {
    var ef = new File(D.checks + '/ERROR.txt'); ef.encoding = 'UTF-8'; ef.open('w'); ef.writeln('失敗: ' + stage + ' / ' + err.toString() + ' / 行 ' + err.line); ef.close();
  }
})();
