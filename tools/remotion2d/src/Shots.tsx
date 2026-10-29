import React from "react";
import { AbsoluteFill, Audio, Img, staticFile, useCurrentFrame, useVideoConfig, Easing, delayRender, continueRender } from "remotion";

// S7 샷 단위 렌더(콘티 2판, 10-29) — 샷마다 연출 컴포넌트. 모든 시각은 샷 안 초, beats 도 샷 안 초(s7_prep 이 바꿈).
// 사장님 «양쪽으로 움직이는 키프레임만 주지말고 서로 내용에맞게 상호작용» → 원인 → 결과가 보이게.
// 금액 숫자는 말에 나온 것만(50만·30만·20만·300~400만). 나머지 거래 금액은 은행 앱식 가림(●●●).

const fh = delayRender("Pretendard");
Promise.all([
  new FontFace("PB", `url(${staticFile("fonts/Pretendard-Bold.otf")})`).load(),
  new FontFace("PXB", `url(${staticFile("fonts/Pretendard-ExtraBold.otf")})`).load(),
  new FontFace("PBL", `url(${staticFile("fonts/Pretendard-Black.otf")})`).load(),
]).then((fs) => { fs.forEach((f) => (document as any).fonts.add(f)); continueRender(fh); }).catch(() => continueRender(fh));

const W = 1080, H = 1920;
const eo = Easing.out(Easing.cubic);
const eio = Easing.inOut(Easing.cubic);
const cl = (x: number) => Math.min(Math.max(x, 0), 1);
const iv = (t: number, a: number, b: number, e = eo) => e(cl((t - a) / Math.max(b - a, 1e-6)));
const mix = (a: number, b: number, u: number) => a + (b - a) * u;
const won = (n: number) => Math.round(n).toLocaleString("ko-KR");
const rnd = (n: number) => { const v = Math.sin(n * 12.9898) * 43758.5453; return v - Math.floor(v); };

export type Shot = { type: string; start: number; end: number; beats: Record<string, number>; img: Record<string, string>; scr?: Record<string, [number, number, number, number]>; size?: Record<string, [number, number]>; p?: any };
export type ShotPlan = { fps: number; duration: number; voice: string; shots: Shot[]; captions: { start: number; end: number; text: string }[]; grade?: [number, number]; title?: [string, string]; brush?: string };

// 그림 하나를 화면 상자(cx,cy,w)에 놓는다 — w 는 그려질 폭
const Pic: React.FC<{ src: string; cx: number; cy: number; w: number; r?: number; o?: number; style?: React.CSSProperties }> = ({ src, cx, cy, w, r = 0, o = 1, style }) => (
  <Img src={staticFile(src)} style={{ position: "absolute", left: 0, top: 0, width: w, transform: `translate(${cx}px, ${cy}px) translate(-50%, -50%) rotate(${r}deg)`, opacity: o, ...style }} />
);
// 화면 꽉 채우는 배경(살짝 밀기)
const Full: React.FC<{ src: string; t: number; dur: number; z0?: number; z1?: number; o?: number; filter?: string }> = ({ src, t, dur, z0 = 1.0, z1 = 1.05, o = 1, filter }) => (
  <Img src={staticFile(src)} style={{ position: "absolute", left: 0, top: 0, width: W, height: H, objectFit: "cover", transform: `scale(${mix(z0, z1, cl(t / dur))})`, opacity: o, filter }} />
);

// 그림 안 흰 화면 사각형(정규화 x,y,w,h) → 그려진 그림 기준 화면 좌표
function screenBox(sh: Shot, key: string, cx: number, cy: number, w: number) {
  const [nx, ny, nw, nh] = sh.scr![key];
  const [iw, ih] = sh.size![key];
  const h = (w * ih) / iw;
  return { x: cx - w / 2 + nx * w, y: cy - h / 2 + ny * h, w: nw * w, h: nh * h };
}
const Box: React.FC<{ b: { x: number; y: number; w: number; h: number }; radius?: number; children: React.ReactNode; bg?: string }> = ({ b, radius = 0, children, bg = "#fff" }) => (
  <div style={{ position: "absolute", left: b.x, top: b.y, width: b.w, height: b.h, overflow: "hidden", borderRadius: radius, background: bg }}>{children}</div>
);

// ---------- 은행 앱 화면(코드) ----------
const BankApp: React.FC<{ w: number; h: number; t: number; b: Record<string, number> }> = ({ w, h, t, b }) => {
  const s = w / 330; // 330 폭 기준으로 그림(글자 크게)
  const bal = t < b.sent ? 500000 : mix(500000, 200000, iv(t, b.sent, b.sent + 0.8));
  const appOn = iv(t, b.open, b.open + 0.25);
  const ban = t < b.open ? iv(t, b.notify, b.notify + 0.3) : 1 - appOn;
  const row = iv(t, b.transfer, b.transfer + 0.3);
  const press = t >= b.press && t < b.press + 0.35 ? 1 - cl((t - b.press) / 0.35) : 0;
  const flyU = iv(t, b.sent, b.sent + 0.5);
  return (
    <div style={{ width: 330, height: h / s, transform: `scale(${s})`, transformOrigin: "0 0", fontFamily: "PB", background: "#f3f4f7", position: "relative" }}>
      {/* 홈 화면(알림 전) */}
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(160deg,#283353,#1b2238)", opacity: 1 - appOn }} />
      {/* 입금 알림 */}
      <div style={{ position: "absolute", left: 14, right: 14, top: mix(-110, 40, ban), height: 92, borderRadius: 18, background: "rgba(255,255,255,0.97)", boxShadow: "0 8px 24px rgba(0,0,0,.25)", display: "flex", alignItems: "center", padding: "0 18px", gap: 14 }}>
        <div style={{ width: 44, height: 44, borderRadius: 12, background: "#cd6932" }} />
        <div><div style={{ fontSize: 17, color: "#7a7f8c" }}>입금</div><div style={{ fontSize: 28, color: "#1d2233", fontFamily: "PXB" }}>500,000원</div></div>
      </div>
      {/* 앱 */}
      <div style={{ position: "absolute", inset: 0, opacity: appOn }}>
        <div style={{ margin: "70px 22px 0", borderRadius: 22, background: "#1f2a48", color: "#fff", padding: "26px 26px", position: "relative" }}>
          <div style={{ fontSize: 18, opacity: 0.7 }}>잔액</div>
          <div style={{ fontSize: 38, fontFamily: "PXB", marginTop: 6, whiteSpace: "nowrap" }}>{won(bal)}원</div>
          {t >= b.sent && flyU < 1 && <div style={{ position: "absolute", right: 26, top: mix(220, 40, flyU), fontSize: 30, color: "#ff6b5a", fontFamily: "PXB", opacity: 1 - flyU }}>−300,000</div>}
        </div>
        <div style={{ margin: "22px 22px 0", borderRadius: 18, background: "#fff", padding: "20px 22px", opacity: row, transform: `translateY(${(1 - row) * 30}px)` }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 22, color: "#1d2233" }}><span>광고비</span><span style={{ color: "#d4483a" }}>−300,000원</span></div>
          <div style={{ marginTop: 18, height: 58, borderRadius: 14, background: t >= b.press ? "#cd6932" : "#e7e9ef", color: t >= b.press ? "#fff" : "#1d2233", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, transform: `scale(${1 - press * 0.06})` }}>
            {t >= b.sent ? "보냄" : "보내기"}
          </div>
        </div>
      </div>
    </div>
  );
};

// 거래내역(사업자 통장, 10-29 «진짜 사업체 느낌» «돈 예시를 하나 둬서 빠지는느낌») — 예시 금액(화면에 «예시» 표시)
// 줄이 위에서 밀려 들어올 때마다 잔액이 그 금액만큼 세어 내려간다. 0 아래로 가면 빨강
type Row = [number, string, number]; // [샷 안 초, 적요, 출금액]
const Statement: React.FC<{ w: number; h: number; t: number; rows: Row[]; start: number; pulse?: number }> = ({ w, h, t, rows, start, pulse = -9 }) => {
  const s = w / 330;
  const shown = rows.filter((r) => t >= r[0]);
  let bal = start;
  rows.forEach((r) => { if (t >= r[0]) bal -= r[2] * iv(t, r[0] + 0.12, r[0] + 0.7); });
  const after: number[] = []; let acc = start; rows.forEach((r) => { acc -= r[2]; after.push(acc); });
  const red = bal < 0;
  const pu = t >= pulse && t < pulse + 0.4 ? Math.sin(cl((t - pulse) / 0.4) * Math.PI) : 0;
  return (
    <div style={{ width: 330, height: h / s, transform: `scale(${s})`, transformOrigin: "0 0", fontFamily: "PB", background: "#eef0f4", position: "relative", overflow: "hidden" }}>
      <div style={{ height: 44, background: "#1f2a48", color: "#fff", display: "flex", alignItems: "center", padding: "0 16px", fontSize: 14, marginTop: 34, justifyContent: "space-between" }}>
        <span>기업뱅킹 · 거래내역</span><span style={{ background: "#cd6932", borderRadius: 6, padding: "2px 8px", fontSize: 12 }}>예시</span>
      </div>
      <div style={{ margin: "12px 14px 0", borderRadius: 14, background: "#fff", padding: "14px 16px", boxShadow: "0 2px 6px rgba(0,0,0,.06)", transform: `scale(${1 + pu * 0.04})`, transformOrigin: "50% 50%" }}>
        <div style={{ fontSize: 13, color: "#7a7f8c" }}>○○마케팅 · 사업자 입출금</div>
        <div style={{ fontSize: 12, color: "#9aa0ad", marginTop: 2 }}>○○○-○○○○○○-○○</div>
        <div style={{ fontSize: 30, fontFamily: "PXB", marginTop: 8, color: red ? "#d4483a" : "#1d2233", whiteSpace: "nowrap" }}>{bal < 0 ? "−" : ""}{won(Math.abs(bal))}원</div>
      </div>
      <div style={{ margin: "12px 14px 0", fontSize: 12, color: "#7a7f8c", display: "flex", justifyContent: "space-between" }}><span>출금</span><span>잔액</span></div>
      <div style={{ margin: "6px 14px 0" }}>
        {shown.slice().reverse().map((r) => {
          const i = rows.indexOf(r);
          const u = iv(t, r[0], r[0] + 0.25);
          return (
            <div key={i} style={{ background: "#fff", borderRadius: 10, padding: "10px 12px", marginBottom: 6, opacity: u, transform: `translateY(${(1 - u) * -30}px)` }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15, color: "#1d2233" }}><span>{r[1]}</span><span style={{ color: "#d4483a", fontFamily: "PXB" }}>−{won(r[2])}</span></div>
              <div style={{ textAlign: "right", fontSize: 12, color: after[i] < 0 ? "#d4483a" : "#9aa0ad", marginTop: 2 }}>{after[i] < 0 ? "−" : ""}{won(Math.abs(after[i]))}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ---------- 샷들 ----------
type SP = { sh: Shot; t: number };

const Calendar: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats, n = 9;
  return (
    <AbsoluteFill>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} filter="blur(6px) brightness(0.8)" />
      {Array.from({ length: n }).map((_, i) => {
        const k = n - 1 - i; // 위에 있는 장부터 넘어감
        const st = b.flip + k * mix(0.16, 0.09, k / n);
        const u = iv(t, st, st + 0.22, eio);
        if (u >= 1) return null;
        return (
          <Img key={i} src={staticFile(sh.img.page)} style={{ position: "absolute", left: 540 - 330, top: 520, width: 660,
            transform: `perspective(1800px) rotateX(${u * 115}deg)`, transformOrigin: "50% 4%", opacity: 1 - cl((u - 0.7) / 0.3), filter: `brightness(${1 - k * 0.012})` }} />
        );
      })}
    </AbsoluteFill>
  );
};

const Phone: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats;
  const z = iv(t, b.zoomout, b.zoomout + 0.9, eio); // 폰 클로즈업 → 인물
  const pw = mix(860, 300, z), pcx = mix(540, sh.p.handX, z), pcy = mix(1080, sh.p.handY, z);
  const sb = screenBox(sh, "phone", pcx, pcy, pw);
  return (
    <AbsoluteFill>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} filter={`blur(${mix(8, 0, z)}px)`} />
      {z > 0 && <Pic src={sh.img.char} cx={sh.p.charX} cy={mix(1300, sh.p.charY, z)} w={sh.p.charW} o={z} />}
      <Pic src={sh.img.phone} cx={pcx} cy={pcy} w={pw} o={1 - z} />
      <Box b={sb} radius={10 * (pw / 300)}><BankApp w={sb.w} h={sb.h} t={t} b={b} /></Box>
    </AbsoluteFill>
  );
};

// 2×2 분할 — 단어마다 칸이 들어오고 칸 안에서 일이 일어난다. collapse 에 칸이 떨어져 나가고 밤 사무실
const Split: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats;
  const cells = [
    { k: "p1", x: 0, y: 460, from: [-560, 0] },
    { k: "p2", x: 540, y: 460, from: [560, 0] },
    { k: "p3", x: 0, y: 900, from: [-560, 0] },
    { k: "p4", x: 540, y: 900, from: [560, 0] },
  ];
  const cw = 540, ch = 440;
  return (
    <AbsoluteFill style={{ background: "#141824" }}>
      <Full src={sh.img.night} t={t} dur={sh.end - sh.start} z0={1.08} z1={1.0} o={iv(t, b.collapse, b.collapse + 0.6)} />
      {cells.map((c, i) => {
        const t0 = b[c.k];
        if (t < t0) return null;
        const u = iv(t, t0, t0 + 0.28);
        const fall = iv(t, b.collapse + i * 0.08, b.collapse + i * 0.08 + 0.55, Easing.in(Easing.quad));
        const lt = t - t0;
        const X = c.x + (1 - u) * c.from[0], Y = c.y + fall * 1500;
        return (
          <div key={c.k} style={{ position: "absolute", left: X, top: Y, width: cw, height: ch, overflow: "hidden", border: "6px solid #141824", boxSizing: "border-box", transform: `rotate(${fall * (i % 2 ? 14 : -12)}deg)` }}>
            <Img src={staticFile(sh.img[c.k])} style={{ position: "absolute", left: "50%", top: "50%", width: cw * 1.25, transform: `translate(-50%,-50%) scale(${mix(1.0, 1.08, cl(lt / 3))})` }} />
            {c.k === "p1" && <Viewfinder w={cw} h={ch} lt={lt} />}
            {c.k === "p2" && <Typing w={cw} h={ch} lt={lt} sh={sh} />}
            {c.k === "p3" && <Graph w={cw} h={ch} lt={lt} sh={sh} />}
            {c.k === "p4" && <Timeline w={cw} h={ch} lt={lt} />}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
const Viewfinder: React.FC<{ w: number; h: number; lt: number }> = ({ w, h, lt }) => {
  const f = iv(lt, 0.25, 0.6); // 초점 상자가 제품으로 좁혀짐
  const bw = mix(300, 140, f), bh = mix(300, 190, f);
  return (
    <svg width={w} height={h} style={{ position: "absolute", left: 0, top: 0 }}>
      {[[30, 30, 1, 1], [w - 30, 30, -1, 1], [30, h - 30, 1, -1], [w - 30, h - 30, -1, -1]].map(([x, y, sx, sy], i) => (
        <path key={i} d={`M${x} ${y + 50 * sy} L${x} ${y} L${x + 50 * sx} ${y}`} stroke="#fff" strokeWidth={5} fill="none" />
      ))}
      <circle cx={58} cy={64} r={11} fill="#ff3b30" opacity={Math.floor(lt * 2) % 2 ? 0.35 : 1} />
      <rect x={w / 2 - bw / 2} y={h / 2 - bh / 2 + 10} width={bw} height={bh} stroke={f >= 1 ? "#7fd1a8" : "#fff"} strokeWidth={4} fill="none" />
    </svg>
  );
};
const Typing: React.FC<{ w: number; h: number; lt: number; sh: Shot }> = ({ w, h, lt, sh }) => {
  // 노트북 화면(그림 기준 비율) 안 광고 관리 화면: 칸이 차고 → 게시 버튼이 눌려 초록
  const [nx, ny, nw, nh] = sh.scr!.p2; const [iw, ih] = sh.size!.p2;
  const dw = w * 1.25, dh = (dw * ih) / iw; const ox = w / 2 - dw / 2, oy = h / 2 - dh / 2;
  const sx = ox + nx * dw, sy = oy + ny * dh, sw = nw * dw, shh = nh * dh;
  const fill = [0, 1, 2].map((i) => iv(lt, 0.1 + i * 0.18, 0.3 + i * 0.18));
  const pressed = lt > 0.85;
  return (
    <div style={{ position: "absolute", left: sx, top: sy, width: sw, height: shh, background: "#f4f5f8", padding: sw * 0.07, boxSizing: "border-box" }}>
      {fill.map((u, i) => <div key={i} style={{ height: shh * 0.12, marginBottom: shh * 0.05, borderRadius: 6, background: "#e3e6ee" }}><div style={{ width: `${u * (90 - i * 15)}%`, height: "100%", borderRadius: 6, background: "#9aa6c4" }} /></div>)}
      <div style={{ marginTop: shh * 0.04, width: "45%", height: shh * 0.16, borderRadius: 8, background: pressed ? "#3fb97a" : "#cd6932", transform: `scale(${lt > 0.8 && lt < 0.95 ? 0.92 : 1})` }} />
    </div>
  );
};
const Graph: React.FC<{ w: number; h: number; lt: number; sh: Shot }> = ({ w, h, lt, sh }) => {
  const [nx, ny, nw, nh] = sh.scr!.p3; const [iw, ih] = sh.size!.p3;
  const dw = w * 1.25, dh = (dw * ih) / iw; const ox = w / 2 - dw / 2, oy = h / 2 - dh / 2;
  const sx = ox + nx * dw, sy = oy + ny * dh, sw = nw * dw, shh = nh * dh;
  const pts = [0.85, 0.7, 0.75, 0.52, 0.58, 0.36, 0.25].map((v, i, a) => [sw * (0.08 + (0.84 * i) / (a.length - 1)), shh * v]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");
  const u = iv(lt, 0.05, 0.9, Easing.inOut(Easing.quad));
  const len = 2000;
  const k = Math.min(Math.floor(u * (pts.length - 1)), pts.length - 2), f = u * (pts.length - 1) - k;
  const dot = [mix(pts[k][0], pts[k + 1][0], f), mix(pts[k][1], pts[k + 1][1], f)];
  return (
    <svg style={{ position: "absolute", left: sx, top: sy }} width={sw} height={shh}>
      <rect width={sw} height={shh} fill="#f4f5f8" />
      {[0.25, 0.5, 0.75].map((y) => <line key={y} x1={0} x2={sw} y1={shh * y} y2={shh * y} stroke="#dde1ea" strokeWidth={2} />)}
      <path d={d} stroke="#cd6932" strokeWidth={6} fill="none" strokeDasharray={len} strokeDashoffset={len * (1 - u * 0.62 - 0.38 * (u >= 1 ? 1 : u))} strokeLinejoin="round" />
      <circle cx={dot[0]} cy={dot[1]} r={9} fill="#1f2a48" />
    </svg>
  );
};
const Timeline: React.FC<{ w: number; h: number; lt: number }> = ({ w, h, lt }) => {
  // 편집 타임라인: 조각 셋이 끌려와 맞물림
  const y = h - 150;
  const clips = [[40, 150, "#cd6932"], [200, 120, "#7f8db0"], [330, 160, "#3fb97a"]] as const;
  return (
    <div style={{ position: "absolute", left: 20, right: 20, top: y, height: 120, borderRadius: 12, background: "rgba(20,24,36,.88)" }}>
      {clips.map(([x, cw, c], i) => {
        const u = iv(lt, 0.1 + i * 0.15, 0.4 + i * 0.15);
        return <div key={i} style={{ position: "absolute", top: 34 + (1 - u) * -70, left: x + (1 - u) * 60, width: cw, height: 52, borderRadius: 8, background: c, opacity: u }} />;
      })}
      <div style={{ position: "absolute", top: 12, bottom: 12, width: 4, background: "#fff", left: mix(30, w - 60, cl(lt / 1.2)) }} />
    </div>
  );
};

const Still: React.FC<SP> = ({ sh, t }) => <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} z0={1.0} z1={1.06} />;

// 위에서 본 사무실: 어둠 속 책상 조명이 하나씩 켜진다(직원 3명)
const Topdown: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats, P = sh.p.desks as [number, number][];
  const lights = [b.l1, b.l2, b.l3].map((x) => iv(t, x, x + 0.25));
  const mask = P.map(([x, y], i) => `radial-gradient(circle ${mix(0, 300, lights[i])}px at ${x}px ${y}px, transparent 55%, black 100%)`).join(",");
  return (
    <AbsoluteFill>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} z0={1.04} z1={1.0} />
      <div style={{ position: "absolute", inset: 0, background: "rgba(8,10,18,.82)", WebkitMaskImage: mask, WebkitMaskComposite: "source-in", maskComposite: "intersect" as any }} />
    </AbsoluteFill>
  );
};

// 광고주 관리 화면(10-29 «종이가아니라 사업자느낌으로 … DB성과데이터라던가») — 관리 업체 수가 1→40 세어 오르고
// 줄이 점점 빠르게 쌓이며 스크롤. 업체명은 ○○, DB 수치는 지어내지 않고 막대
const INDS = ["병원", "분양", "대출", "보험", "프랜차이즈", "건기식", "금융", "학원"];
const Clients: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats, n = 40, span = b.end - b.start;
  const mon = { cx: 540, cy: 900, w: 1400 };
  const sb = screenBox(sh, "bg", mon.cx, mon.cy, mon.w);
  const land = (i: number) => b.start + span * Math.pow(i / n, 0.55);
  const k = Array.from({ length: n }).filter((_, i) => t >= land(i)).length;
  const s = sb.w / 520, rowH = 34;
  const visible = Math.floor((sb.h / s - 96) / rowH);
  const scroll = Math.max(0, k - visible) * rowH;
  return (
    <AbsoluteFill>
      <Full src={sh.img.room} t={t} dur={sh.end - sh.start} filter="blur(6px) brightness(0.8)" />
      <Pic src={sh.img.bg} cx={mon.cx} cy={mon.cy} w={mon.w} />
      <Box b={sb}>
        <div style={{ width: 520, height: sb.h / s, transform: `scale(${s})`, transformOrigin: "0 0", fontFamily: "PB", background: "#f4f5f8", position: "relative", overflow: "hidden" }}>
          <div style={{ height: 52, background: "#1f2a48", color: "#fff", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 18px", fontSize: 18 }}>
            <span>광고주 관리</span>
            <span style={{ background: k >= n ? "#d4483a" : "#cd6932", borderRadius: 8, padding: "3px 12px", fontFamily: "PXB" }}>관리 업체 {k}</span>
          </div>
          <div style={{ display: "flex", padding: "10px 18px 6px", fontSize: 12, color: "#8a90a0" }}><span style={{ width: 150 }}>광고주</span><span style={{ width: 110 }}>업종</span><span style={{ flex: 1 }}>DB 유입</span><span style={{ width: 50 }}>상태</span></div>
          <div style={{ position: "absolute", left: 0, right: 0, top: 96, bottom: 0, overflow: "hidden" }}><div style={{ transform: `translateY(${-scroll}px)` }}>
            {Array.from({ length: k }).map((_, i) => {
              const u = iv(t, land(i), land(i) + 0.15);
              const r = rnd(i + 3);
              return (
                <div key={i} style={{ height: rowH - 4, margin: "0 12px 4px", borderRadius: 6, background: "#fff", display: "flex", alignItems: "center", padding: "0 8px", fontSize: 14, color: "#1d2233", opacity: u, transform: `translateX(${(1 - u) * 40}px)` }}>
                  <span style={{ width: 150 }}>○○{INDS[i % INDS.length]}</span>
                  <span style={{ width: 110 }}><span style={{ fontSize: 11, background: "#e7e9ef", borderRadius: 5, padding: "2px 7px" }}>{INDS[i % INDS.length]}</span></span>
                  <span style={{ flex: 1 }}><span style={{ display: "inline-block", height: 8, borderRadius: 4, width: `${20 + r * 70}%`, background: "#9aa6c4" }} /></span>
                  <span style={{ width: 50 }}><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: r > 0.55 ? "#e9a23b" : "#3fb97a" }} /></span>
                </div>
              );
            })}
          </div></div>
        </div>
      </Box>
    </AbsoluteFill>
  );
};

// 모니터 시안에 반려 도장 → 구긴 종이가 휴지통 테에 맞고 튀어나감
const Reject: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats;
  const mon = { cx: 540, cy: 900, w: 1400 };
  const sb = screenBox(sh, "bg", mon.cx, mon.cy, mon.w);
  const st = iv(t, b.stamp, b.stamp + 0.14, Easing.in(Easing.quad));
  // 종이: 왼쪽 아래에서 던져져 휴지통 테(binX-60, binY-70)에 맞고 바깥으로 튐
  const binX = 860, binY = 1260;
  const p0 = [120, 1350], hit = [binX - 70, binY - 95], p2 = [1040, 1330];
  let px = -999, py = -999, rot = 0;
  if (t >= b.throw) {
    const u = cl((t - b.throw) / 0.55);
    if (u < 1) { px = mix(p0[0], hit[0], u); py = mix(p0[1], hit[1], u) - 260 * Math.sin(Math.PI * u); rot = u * 400; }
    else { const v = cl((t - b.throw - 0.55) / 0.5); px = mix(hit[0], p2[0], v); py = mix(hit[1], p2[1], v) - 140 * Math.sin(Math.PI * v); rot = 400 + v * 300; }
  }
  const binTip = t >= b.throw + 0.55 && t < b.throw + 0.75 ? Math.sin(cl((t - b.throw - 0.55) / 0.2) * Math.PI) * 3 : 0;
  return (
    <AbsoluteFill>
      {sh.img.room && <Full src={sh.img.room} t={t} dur={sh.end - sh.start} filter="blur(6px) brightness(0.8)" />}
      <Pic src={sh.img.bg} cx={mon.cx} cy={mon.cy} w={mon.w} />
      <Box b={sb}>
        <Img src={staticFile(sh.img.thumb)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: t >= b.stamp ? "grayscale(0.6) brightness(0.8)" : "none" }} />
        {t >= b.stamp && (
          <svg width={sb.w} height={sb.h} style={{ position: "absolute", left: 0, top: 0 }}>
            <g transform={`translate(${sb.w / 2} ${sb.h / 2}) scale(${mix(2.2, 1, st)}) rotate(-12)`} opacity={st}>
              <rect x={-110} y={-110} width={220} height={220} rx={26} fill="none" stroke="#d93a2f" strokeWidth={16} />
              <path d="M-60 -60 L60 60 M60 -60 L-60 60" stroke="#d93a2f" strokeWidth={22} strokeLinecap="round" />
            </g>
          </svg>
        )}
      </Box>
      <Pic src={sh.img.bin} cx={binX} cy={binY} w={260} r={binTip} />
      {px > -900 && <Pic src={sh.img.ball} cx={px} cy={py} w={90} r={rot} />}
    </AbsoluteFill>
  );
};

// 타임랩스: 낮 → 밤, 시계 빨리, 커피컵이 책상에 쌓인다
const Timelapse: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats, dur = sh.end - sh.start;
  const night = iv(t, b.start, b.start + 1.4, Easing.linear);
  const cups = (sh.p.cups as [number, number, number][]);
  const a1 = 360 * 1.6 * t;
  return (
    <AbsoluteFill>
      <Full src={sh.img.day} t={t} dur={dur} />
      <Full src={sh.img.night} t={t} dur={dur} o={night} />
      <Pic src={sh.img.desks} cx={540} cy={1120} w={1040} />
      {cups.map(([x, y, ct], i) => t >= ct && <Pic key={i} src={sh.img.cup} cx={x} cy={y - (1 - iv(t, ct, ct + 0.15)) * 60} w={56} />)}
      <Pic src={sh.img.clock} cx={880} cy={580} w={220} />
      <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0 }}>
        <g transform="translate(880 580)">
          <line y2={-52} stroke="#282c3a" strokeWidth={8} strokeLinecap="round" transform={`rotate(${a1 / 12})`} />
          <line y2={-80} stroke="#282c3a" strokeWidth={5} strokeLinecap="round" transform={`rotate(${a1})`} />
          <circle r={7} fill="#cd6932" />
        </g>
      </svg>
    </AbsoluteFill>
  );
};

// 직원 셋 고개가 차례로 떨어짐(앉은 그림 → 엎드린 그림, 떨어지는 4프레임)
const Heads: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats, xs = [190, 540, 890];
  return (
    <AbsoluteFill>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} filter="brightness(0.75)" />
      {["a", "b", "c"].map((k, i) => {
        const hb = [b.h1, b.h2, b.h3][i];
        const down = t >= hb;
        const drop = down ? (1 - iv(t, hb, hb + 0.13, Easing.in(Easing.quad))) * -14 : 0;
        return <Pic key={k} src={down ? sh.img["d" + k] : sh.img["s" + k]} cx={xs[i]} cy={1150 + drop} w={340} />;
      })}
    </AbsoluteFill>
  );
};

const StatementShot: React.FC<SP> = ({ sh, t }) => {
  const pw = 860, pcx = 540, pcy = 1080;
  const fallU = sh.beats.drop !== undefined ? iv(t, sh.beats.drop, sh.beats.drop + 0.5, Easing.in(Easing.quad)) : 0;
  const py = pcy + fallU * 1400, rot = fallU * 20;
  const sb = screenBox(sh, "phone", pcx, py, pw);
  const rows = (sh.p.rows as [string, string, number][]).map(([k, lab, amt]) => [sh.beats[k], lab, amt] as Row);
  return (
    <AbsoluteFill>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} filter="blur(8px) brightness(0.7)" />
      {sh.img.char && fallU > 0 && <Pic src={sh.img.char} cx={540} cy={1040} w={620} o={fallU} />}
      <div style={{ position: "absolute", inset: 0, transform: `rotate(${rot}deg)`, transformOrigin: `${pcx}px ${py}px` }}>
        <Pic src={sh.img.phone} cx={pcx} cy={py} w={pw} />
        <Box b={sb} radius={30}><Statement w={sb.w} h={sb.h} t={t} rows={rows} start={sh.p.start} pulse={sh.beats.rev} /></Box>
      </div>
    </AbsoluteFill>
  );
};

// 계산기 두드리는 손 — 누를 때마다 손끝에 눌림 고리가 퍼진다(숫자는 지어내지 않음)
const Calc: React.FC<SP> = ({ sh, t }) => {
  const taps = sh.p.taps as number[];
  const [fx, fy] = sh.p.finger as number[];
  return (
    <AbsoluteFill>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} z0={1.08} z1={1.0} />
      <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0 }}>
        {taps.filter((x) => t >= x && t < x + 0.35).map((x) => { const u = cl((t - x) / 0.35); return <circle key={x} cx={fx} cy={fy} r={mix(10, 70, eo(u))} fill="none" stroke="#ffd9a8" strokeWidth={5} opacity={1 - u} />; })}
      </svg>
    </AbsoluteFill>
  );
};


// 후킹 ① 입금 알림이 쏟아지고 잔액이 2,500만(말)까지 치솟는다 — 보낸 곳은 ○○, 건별 금액은 가림
const HookPhone: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats, pw = 860, pcx = 540, pcy = 1080;
  const sb = screenBox(sh, "phone", pcx, pcy, pw);
  const s = sb.w / 330;
  const n = 9, span = b.end - b.start;
  const at = (i: number) => b.start + span * Math.pow(i / n, 0.7);
  const bal = 25000000 * iv(t, b.start, b.end, Easing.inOut(Easing.quad));
  const names = ["○○병원", "○○분양", "○○대출", "○○보험", "○○학원", "○○병원", "○○프랜차이즈", "○○금융", "○○건기식"];
  const shown = Array.from({ length: n }).map((_, i) => i).filter((i) => t >= at(i)).reverse();
  return (
    <AbsoluteFill>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} filter="blur(8px) brightness(0.75)" />
      <Pic src={sh.img.phone} cx={pcx} cy={pcy} w={pw} />
      <Box b={sb} radius={30}>
        <div style={{ width: 330, height: sb.h / s, transform: `scale(${s})`, transformOrigin: "0 0", fontFamily: "PB", background: "linear-gradient(160deg,#283353,#1b2238)", position: "relative", overflow: "hidden" }}>
          <div style={{ marginTop: 40, textAlign: "center", color: "#fff" }}>
            <div style={{ fontSize: 14, opacity: 0.7 }}>이번 달 입금</div>
            <div style={{ fontSize: 34, fontFamily: "PXB", whiteSpace: "nowrap" }}>{won(bal)}원</div>
          </div>
          <div style={{ position: "absolute", left: 12, right: 12, top: 130 }}>
            {shown.map((i) => {
              const u = iv(t, at(i), at(i) + 0.18);
              return (
                <div key={i} style={{ height: 52, marginBottom: 6, borderRadius: 12, background: "rgba(255,255,255,.96)", display: "flex", alignItems: "center", gap: 10, padding: "0 12px", transform: `translateY(${(1 - u) * -60}px)`, opacity: u }}>
                  <div style={{ width: 28, height: 28, borderRadius: 8, background: "#cd6932" }} />
                  <div style={{ fontSize: 13, color: "#1d2233" }}>입금 · {names[i]}</div>
                  <div style={{ marginLeft: "auto", fontSize: 13, color: "#2f9e6a", fontFamily: "PXB" }}>+●●●,●●●</div>
                </div>
              );
            })}
          </div>
        </div>
      </Box>
    </AbsoluteFill>
  );
};

// 후킹 ② 매출 대시보드 → «접었어요» 에 화면이 한 줄로 접히며 꺼지고 방이 어두워진다
const HookOff: React.FC<SP> = ({ sh, t }) => {
  const b = sh.beats;
  const off = iv(t, b.off, b.off + 0.22, Easing.in(Easing.cubic));
  const dot = iv(t, b.off + 0.22, b.off + 0.4);
  const [nx, ny, nw, nh] = sh.scr!.bg; const [iw, ih] = sh.size!.bg;
  const w = 1200, h = (w * ih) / iw, x0 = 540 - w / 2, y0 = 1000 - h / 2;
  const sx = x0 + nx * w, sy = y0 + ny * h, sw = nw * w, shh = nh * h;
  const bars = [0.35, 0.5, 0.62, 0.8, 0.95];
  return (
    <AbsoluteFill style={{ background: "#07090f" }}>
      <AbsoluteFill style={{ filter: `brightness(${1 - off * 0.75})` }}>
        <Img src={staticFile(sh.img.bg)} style={{ position: "absolute", left: x0, top: y0, width: w }} />
      </AbsoluteFill>
      <div style={{ position: "absolute", left: sx, top: sy, width: sw, height: shh, background: "#07090f" }}>
        <div style={{ position: "absolute", inset: 0, background: "#f4f5f8", transform: `scaleY(${1 - off * 0.99}) scaleX(${1 - dot})`, opacity: 1 - dot, fontFamily: "PB", padding: sw * 0.06, boxSizing: "border-box" }}>
          <div style={{ fontSize: sw * 0.05, color: "#7a7f8c" }}>월 매출</div>
          <div style={{ fontSize: sw * 0.1, fontFamily: "PXB", color: "#1d2233", whiteSpace: "nowrap" }}>25,000,000원</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: sw * 0.04, height: shh * 0.42, marginTop: shh * 0.04 }}>
            {bars.map((v, i) => <div key={i} style={{ flex: 1, height: `${v * 100 * iv(t, 0.05 + i * 0.08, 0.35 + i * 0.08)}%`, background: i === bars.length - 1 ? "#cd6932" : "#9aa6c4", borderRadius: 6 }} />)}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// 질문 «많이 팔리는 걸 왜 접었을까요?» — 어둠 속 인물에게 조명이 들어오며 다가감
const Question: React.FC<SP> = ({ sh, t }) => {
  const u = iv(t, 0, 0.35);
  return (
    <AbsoluteFill style={{ background: "#07090f" }}>
      <Full src={sh.img.bg} t={t} dur={sh.end - sh.start} z0={1.0} z1={1.08} filter={`blur(6px) brightness(${mix(0.2, 0.6, u)})`} />
      <Pic src={sh.img.char} cx={540} cy={mix(1120, 1060, u)} w={330} o={u} style={{ filter: `brightness(${mix(0.4, 1, u)})` }} />
    </AbsoluteFill>
  );
};

const SHOTS: Record<string, React.FC<SP>> = { hookphone: HookPhone, hookoff: HookOff, question: Question, calendar: Calendar, phone: Phone, split: Split, still: Still, topdown: Topdown, clients: Clients, reject: Reject, timelapse: Timelapse, heads: Heads, statement: StatementShot, calc: Calc };

// 플래시 몽타주: 앞 샷을 그 시각으로 멈춰 0.4초씩 + 흰 번쩍
const Flash: React.FC<SP & { all: Shot[] }> = ({ sh, t, all }) => {
  const refs = sh.p.refs as [number, number][]; // [샷 번호, 그 샷 안 초]
  const seg = (sh.end - sh.start) / refs.length;
  const i = Math.min(Math.floor(t / seg), refs.length - 1);
  const [si, st] = refs[i];
  const C = SHOTS[all[si].type];
  const lt = t - i * seg;
  const fl = 1 - cl(lt / 0.12);
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", inset: 0, transform: `scale(${mix(1.0, 1.06, lt / seg)})` }}><C sh={all[si]} t={st} /></div>
      <AbsoluteFill style={{ background: "#fff", opacity: fl * 0.8 }} />
    </AbsoluteFill>
  );
};


// 제목(10-29 «구피디 썸네일보면 글자에 칠해놓고 이런식으로») — 1줄 흰 글자 + 두꺼운 검정 테두리, 2줄 붓칠 띠 위 검정 글자.
// 띠는 불투명 영역만 잘라(brush_band_tight) 둘째 줄만 덮고, 첫 줄과는 22px 띄운다(10-29 «글자가 안가려지게 … 간격이 너무떨어지면 좀 별로» «위아래 색대비 다르게»)
// 처음 0.35초에 크게 들어와 제자리에 앉고 끝까지 고정
const Title: React.FC<{ lines: [string, string]; brush: string; t: number }> = ({ lines, brush, t }) => {
  const u = iv(t, 0, 0.35);
  const sc = mix(1.25, 1, u);
  const stroke = (px: number): React.CSSProperties => ({ WebkitTextStroke: `${px}px #111`, paintOrder: "stroke fill" } as any);
  return (
    <div style={{ position: "absolute", left: 0, top: 120, width: W, transform: `scale(${sc})`, transformOrigin: "50% 40%", opacity: u, textAlign: "center", fontFamily: "PBL" }}>
      <div style={{ fontSize: 88, color: "#fff", lineHeight: 1.12, ...stroke(16), textShadow: "0 6px 14px rgba(0,0,0,.45)" }}>{lines[0]}</div>
      <div style={{ position: "relative", display: "inline-block", marginTop: 22, padding: "2px 56px 8px" }}>
        <Img src={staticFile(brush)} style={{ position: "absolute", left: -10, top: 0, width: "calc(100% + 20px)", height: "100%", objectFit: "fill" }} />
        <div style={{ position: "relative", fontSize: 96, color: "#141414", lineHeight: 1.12 }}>{lines[1]}</div>
      </div>
    </div>
  );
};

const Caption: React.FC<{ text: string }> = ({ text }) => (
  <div style={{ position: "absolute", left: 0, width: W, top: 1500, transform: "translateY(-50%)", display: "flex", justifyContent: "center" }}>
    <div style={{ background: "rgb(52,52,56)", borderRadius: 12, padding: "14px 26px", fontFamily: "PB", fontSize: 66, lineHeight: 1.2, color: "rgb(245,245,245)", whiteSpace: "pre" }}>{text}</div>
  </div>
);

export const Shots: React.FC<ShotPlan> = (plan) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const idx = Math.max(0, plan.shots.findIndex((s) => t >= s.start && t < s.end));
  const sh = plan.shots[idx] ?? plan.shots[plan.shots.length - 1];
  const lt = t - sh.start;
  const cap = plan.captions.find((c) => t >= c.start && t < c.end);
  const g = plan.grade ? iv(t, plan.grade[0], plan.grade[0] + 0.4) * (t < plan.grade[1] ? 1 : 0) : 0;
  const C = SHOTS[sh.type];
  return (
    <AbsoluteFill style={{ backgroundColor: "#141824" }}>
      <AbsoluteFill style={{ filter: g > 0 ? `sepia(${0.28 * g}) saturate(${1 - 0.25 * g})` : undefined }}>
        {sh.type === "flash" ? <Flash sh={sh} t={lt} all={plan.shots} /> : C ? <C sh={sh} t={lt} /> : null}
      </AbsoluteFill>
      {plan.title && plan.brush && <Title lines={plan.title} brush={plan.brush} t={t} />}
      {cap && <Caption text={cap.text} />}
      <Audio src={staticFile(plan.voice)} />
    </AbsoluteFill>
  );
};
