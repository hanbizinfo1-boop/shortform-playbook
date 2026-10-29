import React from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig, Easing, interpolate, delayRender, continueRender } from "remotion";

// 자막 글꼴을 다 읽은 뒤 그린다(안 그러면 첫 프레임이 기본 글꼴)
const fontHandle = delayRender("Pretendard");
new FontFace("PretendardB", `url(${staticFile("fonts/Pretendard-Bold.otf")})`).load()
  .then((f) => { (document as any).fonts.add(f); continueRender(fontHandle); })
  .catch(() => continueRender(fontHandle));

// S7 2D 재현 설명 쇼츠 — 시각은 전부 장면 안 초(s7_prep.py 가 원본 초에서 바꿔 넣는다)
// 규칙(10-29): 화면 글 없음(자막만) · 떨림 0(소수점 변환, bob 없음) · 사건 간격 ≤1.5초 · 오버슈트 0

type Key = [number, Record<string, number>];
export type Item = {
  kind: "sprite" | "stream" | "pile" | "hands" | "fill";
  t0?: number; t1?: number; depth?: number; intro?: number; fadeOut?: number;
  file?: string; x?: number; y?: number; h?: number; flip?: boolean;
  keys?: Key[]; poses?: [number, string][];
  p0?: [number, number]; p1?: [number, number]; every?: number; travel?: number; spin?: number; tilt?: number; jitter?: number; arc?: number; prefill?: boolean;
  dx?: number; dy?: number; count?: [number, number][]; rot?: number;
  r?: number; speed?: number;
  rect?: [number, number, number, number]; level?: [number, number][];
};
export type Scene = { start: number; end: number; bg?: string; bgDepth?: number; bg2?: { file: string; t0: number; dur: number }; cam?: [number, number, number, number][]; items: Item[] };
export type Caption = { start: number; end: number; text: string };
export type Plan = { fps: number; duration: number; voice: string | null; scenes: Scene[]; captions: Caption[] };

const W = 1080, H = 1920;
const ease = Easing.out(Easing.cubic);

function lerpKeys(keys: [number, ...number[]][], t: number, linear = false): number[] {
  if (t <= keys[0][0]) return keys[0].slice(1) as number[];
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i], b = keys[i + 1];
    if (t < b[0]) {
      let u = (t - a[0]) / Math.max(b[0] - a[0], 1e-6);
      if (!linear) u = ease(u);
      return a.slice(1).map((v, j) => (v as number) + ((b[j + 1] as number) - (v as number)) * u);
    }
  }
  return keys[keys.length - 1].slice(1) as number[];
}

function state(keys: Key[] | undefined, t: number, base: Record<string, number>) {
  if (!keys || !keys.length) return base;
  let prevT = keys[0][0];
  let prev = { ...base, ...keys[0][1] };
  if (t <= prevT) return prev;
  for (let i = 1; i < keys.length; i++) {
    const [kt, kv] = keys[i];
    const cur = { ...prev, ...kv };
    if (t < kt) {
      const u = ease((t - prevT) / Math.max(kt - prevT, 1e-6));
      const o: Record<string, number> = {};
      for (const k of Object.keys(cur)) o[k] = prev[k] + (cur[k] - prev[k]) * u;
      return o;
    }
    prevT = kt; prev = cur;
  }
  return prev;
}

const rnd = (n: number) => { const v = Math.sin(n * 12.9898) * 43758.5453; return v - Math.floor(v); };

// 카메라: 깊이 d 인 점 (x,y) → 화면. 전부 소수점(떨림 없음)
type Cam = { z: number; cx: number; cy: number };
const place = (cam: Cam, x: number, y: number, d: number) => {
  const zz = 1 + (cam.z - 1) * d;
  return { X: W / 2 + (x - W / 2) * zz + cam.cx * d, Y: H / 2 + (y - H / 2) * zz + cam.cy * d, zz };
};

const Spr: React.FC<{ file: string; X: number; Y: number; h: number; s?: number; r?: number; o?: number; flip?: boolean }> = ({ file, X, Y, h, s = 1, r = 0, o = 1, flip }) => (
  <Img
    src={staticFile(file)}
    style={{
      position: "absolute", left: 0, top: 0, height: h, width: "auto",
      transform: `translate(${X}px, ${Y}px) translate(-50%, -50%) rotate(${r}deg) scale(${(flip ? -1 : 1) * s}, ${s})`,
      opacity: o, willChange: "transform",
    }}
  />
);

const ItemView: React.FC<{ it: Item; t: number; cam: Cam }> = ({ it, t, cam }) => {
  const t0 = it.t0 ?? 0;
  if (t < t0 || t >= (it.t1 ?? 1e9)) return null;
  const lt = t - t0;
  const d = it.depth ?? 1;
  const intro = it.intro ?? 0.2;
  const ia = intro ? ease(Math.min(lt / intro, 1)) : 1;
  const fo = it.fadeOut && it.t1 ? Math.min(1, (it.t1 - t) / it.fadeOut) : 1;
  if (it.kind === "sprite") {
    let file = it.file!;
    for (const [pt, pf] of it.poses ?? []) if (t >= pt) file = pf;
    const st = state(it.keys, t, { x: it.x!, y: it.y!, s: 1, r: 0, o: 1 });
    const p = place(cam, st.x, st.y + (1 - ia) * 30, d);
    return <Spr file={file} X={p.X} Y={p.Y} h={it.h! * p.zz} s={st.s} r={st.r} o={st.o * ia * fo} flip={it.flip} />;
  }
  if (it.kind === "stream") {
    const ev = it.every!, tr = it.travel!;
    const out: React.ReactNode[] = [];
    const nMin = it.prefill ? Math.floor(-tr / ev) - 1 : 0;
    for (let n = Math.max(nMin, Math.floor((lt - tr) / ev)); n <= Math.floor(lt / ev); n++) {
      const born = n * ev;
      const u = (lt - born) / tr;
      if (u < 0 || u > 1) continue;
      const r = rnd(n);
      const px = it.p0![0] + (it.p1![0] - it.p0![0]) * u;
      const py = it.p0![1] + (it.p1![1] - it.p0![1]) * u - (it.arc ?? 0) * Math.sin(Math.PI * u) + (r - 0.5) * (it.jitter ?? 0);
      const p = place(cam, px, py, d);
      const fade = Math.min(1, u / 0.08, (1 - u) / 0.08);
      out.push(<Spr key={n} file={it.file!} X={p.X} Y={p.Y} h={it.h! * p.zz * (0.9 + 0.2 * r)} r={(it.spin ?? 0) * (lt - born) + r * (it.tilt ?? 0)} o={fade * fo} />);
    }
    return <>{out}</>;
  }
  if (it.kind === "pile") {
    // 하나씩 위에서 떨어져 쌓인다 — count [[t, n]] (장면 안 초)
    const n = Math.floor(lerpKeys(it.count as any, t, true)[0] + 1e-6);
    const out: React.ReactNode[] = [];
    for (let i = 0; i < n; i++) {
      const bornT = (() => { // i 번째가 생긴 시각(선형 역산)
        const ks = it.count!;
        for (let k = 0; k < ks.length - 1; k++) {
          const [ta, na] = ks[k], [tb, nb] = ks[k + 1];
          if (i + 1 <= nb && i + 1 > na) return ta + ((i + 1 - na) / Math.max(nb - na, 1e-6)) * (tb - ta);
        }
        return -1;
      })();
      const fall = bornT < 0 ? 1 : ease(Math.min((t - bornT) / 0.18, 1));
      const r = rnd(i + 7);
      const p = place(cam, it.x! + (r - 0.5) * 18, it.y! - i * (it.dy ?? 14) - (1 - fall) * 120, d);
      out.push(<Spr key={i} file={it.file!} X={p.X} Y={p.Y} h={it.h! * p.zz} r={(it.rot ?? 0) + (r - 0.5) * 6} o={fall * fo} />);
    }
    return <>{out}</>;
  }
  if (it.kind === "hands") {
    const p = place(cam, it.x!, it.y!, d);
    const R = it.r! * p.zz;
    const a1 = 360 * it.speed! * t, a2 = a1 / 12;
    return (
      <svg style={{ position: "absolute", left: 0, top: 0 }} width={W} height={H}>
        <g transform={`translate(${p.X} ${p.Y})`}>
          <line x1={0} y1={0} x2={0} y2={-R * 0.52} stroke="#282c3a" strokeWidth={8 * p.zz} strokeLinecap="round" transform={`rotate(${a2})`} />
          <line x1={0} y1={0} x2={0} y2={-R * 0.78} stroke="#282c3a" strokeWidth={5 * p.zz} strokeLinecap="round" transform={`rotate(${a1})`} />
          <circle r={7 * p.zz} fill="#cd6932" />
        </g>
      </svg>
    );
  }
  if (it.kind === "fill") {
    const lv = lerpKeys(it.level as any, t, true)[0];
    const [rx, ry, rw, rh] = it.rect!;
    const p = place(cam, rx + rw / 2, ry + rh / 2, d);
    const w = rw * p.zz, h = rh * p.zz;
    return (
      <div style={{ position: "absolute", left: p.X - w / 2, top: p.Y - h / 2, width: w, height: h, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 0, bottom: 0, width: w, height: h * lv, overflow: "hidden" }}>
          <Img src={staticFile(it.file!)} style={{ position: "absolute", left: 0, bottom: 0, width: w, height: h }} />
        </div>
      </div>
    );
  }
  return null;
};

const SceneView: React.FC<{ sc: Scene; t: number }> = ({ sc, t }) => {
  const dur = sc.end - sc.start;
  const [z, cx, cy] = lerpKeys((sc.cam ?? [[0, 1, 0, 0], [dur, 1.06, 0, 0]]) as any, t);
  const cam = { z, cx, cy };
  const bd = sc.bgDepth ?? 0.4;
  const bz = (1 + (z - 1) * bd) * 1.04;
  const bgStyle = (o: number): React.CSSProperties => ({
    position: "absolute", left: 0, top: 0, width: W, height: H, objectFit: "cover", opacity: o,
    transform: `translate(${cx * bd}px, ${cy * bd}px) scale(${bz})`, transformOrigin: "50% 50%",
  });
  const b2 = sc.bg2 ? interpolate(t, [sc.bg2.t0, sc.bg2.t0 + sc.bg2.dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "#141824", overflow: "hidden" }}>
      {sc.bg && <Img src={staticFile(sc.bg)} style={bgStyle(1)} />}
      {sc.bg2 && b2 > 0 && <Img src={staticFile(sc.bg2.file)} style={bgStyle(b2)} />}
      {sc.items.map((it, i) => <ItemView key={i} it={it} t={t} cam={cam} />)}
    </AbsoluteFill>
  );
};

// 자막: A2 불투명 회색 띠 — (52,52,56) · 여백 26/14 · 반경 12 · Pretendard Bold 66 · 흰 245 (s6_render.caption_img 와 같음)
const CaptionView: React.FC<{ text: string }> = ({ text }) => (
  <div style={{ position: "absolute", left: 0, width: W, top: 1500, transform: "translateY(-50%)", display: "flex", justifyContent: "center" }}>
    <div style={{ background: "rgb(52,52,56)", borderRadius: 12, padding: "14px 26px", fontFamily: "PretendardB", fontSize: 66, lineHeight: 1.2, color: "rgb(245,245,245)", whiteSpace: "pre" }}>{text}</div>
  </div>
);

export const Shorts2D: React.FC<Plan> = (plan) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const sc = plan.scenes.find((s) => t >= s.start && t < s.end) ?? plan.scenes[plan.scenes.length - 1];
  const cap = plan.captions.find((c) => t >= c.start && t < c.end);
  return (
    <AbsoluteFill style={{ backgroundColor: "#141824" }}>
      {sc && <SceneView sc={sc} t={t - sc.start} />}
      {cap && <CaptionView text={cap.text} />}
      {plan.voice && <Sequence from={0}><Audio src={staticFile(plan.voice)} /></Sequence>}
    </AbsoluteFill>
  );
};
