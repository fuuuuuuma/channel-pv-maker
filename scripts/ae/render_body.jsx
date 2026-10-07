// 開いているこの案件の .aep の本編コンポを、レンダーキューで ProRes に書き出す（他のプロジェクトが開いていたら何もしない）。
// pv.py ae render が先頭に「var R = {aep_name, comp, out, log};」を付ける。設定は日本語版・英語版の両方の名前を試す。
(function () {
  var log = new File(R.log); log.encoding = 'UTF-8'; log.open('w');
  try {
    var p = app.project;
    if (!p.file || p.file.displayName != R.aep_name) { log.writeln('別のプロジェクトが開いている: ' + (p.file ? p.file.displayName : '名称未設定')); log.close(); return; }
    var c = null; for (var i = 1; i <= p.numItems; i++) if (p.item(i).name == R.comp && p.item(i) instanceof CompItem) c = p.item(i);
    if (!c) { log.writeln('コンポが無い: ' + R.comp); log.close(); return; }
    var rq = p.renderQueue; while (rq.numItems > 0) rq.item(1).remove();
    var it = rq.items.add(c);
    var rs = ['最良設定', 'Best Settings'], om = ['高品質', 'High Quality'];
    for (var a = 0; a < rs.length; a++) { try { it.applyTemplate(rs[a]); break; } catch (e) {} }
    var mo = it.outputModule(1);
    for (var b = 0; b < om.length; b++) { try { mo.applyTemplate(om[b]); break; } catch (e) {} }
    mo.file = new File(R.out);
    log.writeln('開始 ' + (new Date()).toString()); rq.render(); log.writeln('終了 ' + (new Date()).toString() + ' 状態 ' + it.status);
  } catch (e) { log.writeln('失敗 ' + e.toString() + ' 行 ' + e.line); }
  log.close();
})();
