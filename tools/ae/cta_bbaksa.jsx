// S6 엔딩 구독 CTA — 에펙 컴프를 스크립트로 만들고 .aep 로 저장(사장님이 직접 열어 고칠 수 있게).
// 10-15 사장님 «알림설정까지뺴 / 그냥 광고를 잘하고 싶다면? 빡이사 구독 딱 이정도면 좋을거같아 / 빡이사 구독은 에펙이나 리모션으로 잘 만져주고»
// 목소리 없음 — 효과음은 s6_render 계획(sfx at_typo)에서 이 시각에 맞춰 붙인다:
//   0.00 «광고를 잘하고 싶다면?» 한 글자씩 올라옴(소리 없음 — 앞 말끝이 묻히지 않게)
//   0.90 «빡이사» 크게 들어옴(흐림 → 선명, 130% → 100%, 튕김 없음)
//   1.45 빨간 «구독» 버튼 등장
//   1.80~2.15 커서가 버튼으로 → 2.20 누름(눌림 + 물결) → 2.28 회색 «구독중»
//   2.50 «빡이사» 위로 빛 한 번 지나감
// 실행: AfterFX.com -noui -r tools/ae/cta_bbaksa.jsx  (결과: 소재/ae/cta_bbaksa.aep · _tmp/ae/cta_bbaksa.mov)
(function () {
  var ROOT = "C:/Users/user/Desktop/숏폼자동화/";
  var LOG = new File(ROOT + "_tmp/ae/cta_bbaksa.log");
  // 파일 쓰기가 막혀 있어도(환경 설정 «스크립트 파일 쓰기 허용» 꺼짐) 멈추지 않게 — 실패하면 콘솔(write)로만
  function log(m) {
    try { $.writeln(m); } catch (e0) {}
    try { LOG.encoding = "UTF-8"; if (LOG.open("a")) { LOG.writeln(m); LOG.close(); } } catch (e1) {}
  }
  try {
    var ROOT = "C:/Users/user/Desktop/숏폼자동화/";
    var W = 1080, H = 1270, DUR = 4.2, FPS = 30;
    var FONT = "Pretendard-Bold";
    var YELLOW = [1, 0.831, 0], WHITE = [1, 1, 1], RED = [0.93, 0.11, 0.14], GRAY = [0.27, 0.28, 0.31];

    app.beginSuppressDialogs();
    app.newProject();
    var comp = app.project.items.addComp("빡이사구독", W, H, 1, DUR, FPS);

    function ease(prop, idx, outInf, inInf) {
        var t = prop.propertyValueType;
        var dim = (t === PropertyValueType.TwoD) ? 2 : (t === PropertyValueType.ThreeD) ? 3 : 1;
        var e = [], o = [];
        for (var i = 0; i < dim; i++) { e.push(new KeyframeEase(0, inInf)); o.push(new KeyframeEase(0, outInf)); }
        prop.setTemporalEaseAtKey(idx, e, o);
    }
    function keys(prop, ts, vs, inf) {
        for (var i = 0; i < ts.length; i++) prop.setValueAtTime(ts[i], vs[i]);
        for (var k = 1; k <= prop.numKeys; k++) ease(prop, k, inf || 75, inf || 75);
    }
    function text(str, size, color, pos) {
        var L = comp.layers.addText(str);
        var tp = L.property("ADBE Text Properties").property("ADBE Text Document");
        var td = tp.value;
        td.resetCharStyle();
        td.font = FONT;
        td.fontSize = size;
        td.fillColor = color;
        td.applyFill = true;
        td.applyStroke = false;
        td.fauxBold = true;
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.setValue(td);
        L.property("ADBE Transform Group").property("ADBE Position").setValue(pos);
        return L;
    }

    // 바탕: 본편과 같은 무대 — 폭 맞춤, 아주 느린 밀기(100 → 103%)
    var bgItem = app.project.importFile(new ImportOptions(new File(ROOT + "소재/ai/stage/stage_studio.png")));
    var bg = comp.layers.add(bgItem);
    var k0 = W / bgItem.width * 100;
    keys(bg.property("ADBE Transform Group").property("ADBE Scale"), [0, DUR], [[k0, k0], [k0 * 1.03, k0 * 1.03]], 33);
    bg.property("ADBE Transform Group").property("ADBE Position").setValue([W / 2, H / 2]);

    // 1) «광고를 잘하고 싶다면?» — 글자마다 아래에서 올라오며 나타남
    var t1 = text("광고를 잘하고 싶다면?", 88, WHITE, [W / 2, 400]);
    var an = t1.property("ADBE Text Properties").property("ADBE Text Animators").addProperty("ADBE Text Animator");
    var ap = an.property("ADBE Text Animator Properties");
    ap.addProperty("ADBE Text Opacity").setValue(0);
    ap.addProperty("ADBE Text Position 3D").setValue([0, 46, 0]);
    var sel = an.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
    keys(sel.property("ADBE Text Percent Start"), [0.0, 0.55], [0, 100], 60);
    sel.property("ADBE Text Range Advanced").property("ADBE Text Range Shape").setValue(3);   // 위로 경사(Ramp Up) — 부드럽게 이어 나옴
    sel.property("ADBE Text Range Advanced").property("ADBE Text Selector Smoothness").setValue(100);

    // 2) «빡이사» — 크게 들어옴(흐림 → 선명, 130 → 100%)
    var t2 = text("빡이사", 250, YELLOW, [W / 2, 650]);
    t2.inPoint = 0.9;
    var tr2 = t2.property("ADBE Transform Group");
    keys(tr2.property("ADBE Scale"), [0.9, 1.15], [[130, 130], [100, 100]], 85);
    keys(tr2.property("ADBE Opacity"), [0.9, 0.98], [0, 100], 50);
    var blur = t2.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
    keys(blur.property("ADBE Gaussian Blur 2-0001"), [0.9, 1.12], [40, 0], 80);
    var sweep = t2.property("ADBE Effect Parade").addProperty("CC Light Sweep");
    try {
        keys(sweep.property("Center"), [2.5, 2.95], [[-60, 125], [1100, 125]], 50);   // 글자 레이어 좌표
        sweep.property("Direction").setValue(-25);
        sweep.property("Width").setValue(70);
        sweep.property("Sweep Intensity").setValue(60);
    } catch (e) { log("light sweep: " + e); }

    // 3) «구독» 버튼 — 빨강 둥근 판 + 흰 글자(누르면 회색 «구독중»)
    var btn = comp.layers.addShape();
    btn.name = "구독 버튼";
    var g = btn.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
    var gv = g.property("ADBE Vectors Group");
    var rect = gv.addProperty("ADBE Vector Shape - Rect");
    rect.property("ADBE Vector Rect Size").setValue([380, 128]);
    rect.property("ADBE Vector Rect Roundness").setValue(64);
    var fill = gv.addProperty("ADBE Vector Graphic - Fill");
    keys(fill.property("ADBE Vector Fill Color"), [2.2, 2.3], [RED, GRAY], 50);
    btn.inPoint = 1.45;
    var trb = btn.property("ADBE Transform Group");
    trb.property("ADBE Position").setValue([W / 2, 960]);
    keys(trb.property("ADBE Scale"), [1.45, 1.65, 2.2, 2.27, 2.38], [[0, 0], [100, 100], [100, 100], [92, 92], [100, 100]], 80);

    var bt1 = text("구독", 64, WHITE, [0, 22]);
    bt1.parent = btn;
    bt1.property("ADBE Transform Group").property("ADBE Position").setValue([0, 22]);
    bt1.inPoint = 1.45;
    keys(bt1.property("ADBE Transform Group").property("ADBE Opacity"), [2.22, 2.3], [100, 0], 50);
    var bt2 = text("구독중", 60, [0.85, 0.86, 0.88], [0, 21]);
    bt2.parent = btn;
    bt2.property("ADBE Transform Group").property("ADBE Position").setValue([0, 21]);
    bt2.inPoint = 2.22;
    keys(bt2.property("ADBE Transform Group").property("ADBE Opacity"), [2.22, 2.3], [0, 100], 50);

    // 누름 물결
    var rip = comp.layers.addShape();
    rip.name = "누름 물결";
    var rg = rip.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group").property("ADBE Vectors Group");
    var rr = rg.addProperty("ADBE Vector Shape - Rect");
    rr.property("ADBE Vector Rect Size").setValue([380, 128]);
    rr.property("ADBE Vector Rect Roundness").setValue(64);
    var st = rg.addProperty("ADBE Vector Graphic - Stroke");
    st.property("ADBE Vector Stroke Color").setValue(WHITE);
    st.property("ADBE Vector Stroke Width").setValue(6);
    rip.inPoint = 2.2;
    rip.outPoint = 2.7;
    var trr = rip.property("ADBE Transform Group");
    trr.property("ADBE Position").setValue([W / 2, 960]);
    keys(trr.property("ADBE Scale"), [2.2, 2.65], [[100, 100], [128, 140]], 60);
    keys(trr.property("ADBE Opacity"), [2.2, 2.65], [90, 0], 60);
    rip.moveAfter(btn);

    // 커서(흰 화살표 + 검은 테두리) — 오른쪽 아래에서 버튼으로, 누를 때 살짝 작아짐
    var cur = comp.layers.addShape();
    cur.name = "커서";
    var cg = cur.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group").property("ADBE Vectors Group");
    var cp = cg.addProperty("ADBE Vector Shape - Group");
    var sh = new Shape();
    sh.vertices = [[0, 0], [0, 68], [18, 52], [32, 84], [44, 78], [30, 48], [54, 48]];
    sh.closed = true;
    cp.property("ADBE Vector Shape").setValue(sh);
    var cs = cg.addProperty("ADBE Vector Graphic - Stroke");
    cs.property("ADBE Vector Stroke Color").setValue([0.08, 0.08, 0.1]);
    cs.property("ADBE Vector Stroke Width").setValue(5);
    var cf = cg.addProperty("ADBE Vector Graphic - Fill");
    cf.property("ADBE Vector Fill Color").setValue(WHITE);
    cur.inPoint = 1.8;
    var trc = cur.property("ADBE Transform Group");
    keys(trc.property("ADBE Position"), [1.8, 2.15], [[900, 1200], [690, 968]], 80);
    keys(trc.property("ADBE Scale"), [2.18, 2.24, 2.34], [[100, 100], [86, 86], [100, 100]], 70);
    keys(trc.property("ADBE Opacity"), [1.8, 1.9], [0, 100], 50);

    // 저장 + 렌더 대기열(무손실 mov)
    var aep = new File(ROOT + "소재/ae/cta_bbaksa.aep");
    app.project.save(aep);
    var rq = app.project.renderQueue.items.add(comp);
    rq.outputModule(1).applyTemplate("Lossless");
    rq.outputModule(1).file = new File(ROOT + "_tmp/ae/cta_bbaksa.mov");
    app.project.renderQueue.render();
    app.project.save(aep);
    log("ok");
  } catch (err) {
    log("ERROR line " + err.line + ": " + err);
  }
  try { app.endSuppressDialogs(false); } catch (e2) {}
  app.quit();
})();
