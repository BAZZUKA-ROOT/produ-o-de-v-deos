import clsx from "clsx";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { fmtSec } from "@/lib/format";
import type { Project, Scene, Timeline } from "@/lib/types";

const UPPER = new Set(["Anton", "Bebas Neue"]);
const DIMS: Record<string, [number, number]> = { "9:16": [9, 16], "1:1": [1, 1], "16:9": [16, 9], "4:5": [4, 5] };
const ease = (x: number) => x * x * (3 - 2 * x);

function motionTransform(motion: string, p: number) {
  const e = ease(Math.min(Math.max(p, 0), 1));
  const z = 0.22 * 0.85;
  switch (motion) {
    case "zoom_in": return `scale(${1 + z * e})`;
    case "zoom_out": return `scale(${1 + z * (1 - e)})`;
    case "zoom_in_left": return `scale(${1 + z * e}) translateX(${-5 * e}%)`;
    case "zoom_in_right": return `scale(${1 + z * e}) translateX(${5 * e}%)`;
    case "pan_left": return `scale(1.13) translateX(${5 - 10 * e}%)`;
    case "pan_right": return `scale(1.13) translateX(${-5 + 10 * e}%)`;
    case "pan_up": return `scale(1.13) translateY(${5 - 10 * e}%)`;
    case "pan_down": return `scale(1.13) translateY(${-5 + 10 * e}%)`;
    default: return "none";
  }
}

function textStyle(anim: string, local: number): React.CSSProperties {
  const p = Math.min(Math.max(local / 0.38, 0), 1);
  const e = ease(p);
  switch (anim) {
    case "slide_up": return { opacity: e, transform: `translateY(${(1 - e) * 40}%)` };
    case "slide_left": return { opacity: e, transform: `translateX(${(1 - e) * 25}%)` };
    case "pop": { const s = p < 0.6 ? 0.4 + (1.12 - 0.4) * (p / 0.6) : 1.12 - 0.12 * ((p - 0.6) / 0.4); return { opacity: Math.min(1, p * 4), transform: `scale(${s})` }; }
    case "blur_in": return { opacity: e, filter: `blur(${(1 - e) * 10}px)` };
    case "typewriter": { const q = Math.min(local / 1.4, 1); return { clipPath: `inset(0 ${(1 - q) * 100}% 0 0)` }; }
    case "none": return {};
    default: return { opacity: Math.min(local / 0.3, 1) };
  }
}

const PRICE = /(R\$\s?\d[\d.,]*|\d{1,3}\s?%)/i;
const lum = (hex: string) => { const n = parseInt(hex.slice(1), 16); return (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255; };

function TitleView({ text, role, style, font, m, pal, local }: { text: string; role: string; style: string; font: string; m: number; pal: string[]; local: number }) {
  const upper = UPPER.has(font);
  const size = m * (upper ? 0.135 : 0.105);
  const onAccent = lum(pal[2]) > 0.55 ? "#111" : "#fff";
  const grow = Math.min(Math.max((local - 0.25) / 0.45, 0), 1);
  if (role === "offer" && PRICE.test(text) && text.length <= 28) {
    const r = m * 0.26;
    return (
      <div className="relative flex items-center justify-center" style={{ width: r * 2, height: r * 2 }}>
        <svg viewBox="-100 -100 200 200" className="absolute inset-0 drop-shadow-xl" style={{ transform: `rotate(${-8 * Math.min(local / 4, 1)}deg)` }}>
          <polygon fill={pal[2]} points={Array.from({ length: 36 }, (_, i) => { const a = (Math.PI * i) / 18; const rr = i % 2 ? 88 : 100; return `${rr * Math.cos(a)},${rr * Math.sin(a)}`; }).join(" ")} />
        </svg>
        <span className="relative text-center font-black leading-tight" style={{ fontFamily: "Montserrat", fontSize: m * 0.1, color: onAccent, transform: "rotate(-4deg)" }}>{text}</span>
      </div>
    );
  }
  const common: React.CSSProperties = { fontFamily: font, fontSize: size, textTransform: upper ? "uppercase" : undefined };
  if (style === "comercial" || style === "criativo") {
    return <p className="font-bold leading-[1.1]" style={{ ...common, color: onAccent, background: pal[2], padding: "0.12em 0.3em", transform: style === "criativo" ? "rotate(-2.5deg)" : undefined, boxShadow: "0 6px 18px rgba(0,0,0,.35)" }}>{text}</p>;
  }
  const shadow = style === "tecnologico" ? `0 0 ${m * 0.03}px ${pal[2]}, 0 2px 6px #000` : "0 3px 10px rgba(0,0,0,.6), 0 0 2px #000";
  const line = <span className="block" style={{ height: Math.max(2, m / 400), width: m * 0.22 * grow, background: pal[2], margin: "0 auto" }} />;
  return (
    <div className="flex flex-col items-center gap-[0.35em]">
      {style === "elegante" && line}
      <p className="font-bold leading-[1.05]" style={{ ...common, color: pal[3], textShadow: shadow }}>{text}</p>
      {style === "elegante" && line}
      {(style === "moderno" || style === "profissional") && <span className="block rounded-full" style={{ height: Math.max(5, m * 0.014), width: m * 0.16 * grow, background: pal[2] }} />}
    </div>
  );
}

const titleTop = (pos: string, vertical: boolean) => (pos === "top" ? (vertical ? 20 : 18) : pos === "bottom" ? (vertical ? 66 : 62) : vertical ? 42 : 40);

export function Player({ project, timeline, onSelect, time, setTime }: {
  project: Project; timeline: Timeline | undefined; onSelect: (id: string) => void;
  time: number; setTime: (t: number) => void;
}) {
  const s = project.settings;
  const [w, h] = DIMS[s.format] ?? DIMS["9:16"];
  const boxRef = useRef<HTMLDivElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 270, h: 480 });
  const [playing, setPlaying] = useState(false);
  const tRef = useRef(time);
  const audios = useRef(new Map<string, HTMLAudioElement>());
  const music = useRef<HTMLAudioElement | null>(null);
  const total = timeline?.total ?? 0;

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const scale = Math.min(r.width / w, r.height / h);
      setSize({ w: Math.floor(w * scale), h: Math.floor(h * scale) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [w, h]);

  const scenesById = new Map(project.scenes.map((sc) => [sc.id, sc]));
  const musicUrl = project.music?.url ?? null;

  // sincroniza áudio com o relógio
  const syncAudio = useCallback((t: number, isPlaying: boolean) => {
    if (!timeline) return;
    let narrating = false;
    for (const ts of timeline.scenes) {
      const sc = scenesById.get(ts.id);
      const url = sc?.narration_audio?.url;
      if (!url || ts.narr_start == null || !s.narration_enabled) continue;
      let a = audios.current.get(ts.id);
      if (!a || a.src.indexOf(url) < 0) {
        a?.pause();
        a = new Audio(url);
        a.preload = "auto";
        audios.current.set(ts.id, a);
      }
      const inside = t >= ts.narr_start && t < ts.narr_start + (ts.narr_duration ?? 0);
      if (inside) narrating = true;
      a.playbackRate = timeline.tempo;
      if (isPlaying && inside) {
        const want = (t - ts.narr_start) * timeline.tempo;
        if (a.paused) { a.currentTime = want; void a.play().catch(() => {}); }
        else if (Math.abs(a.currentTime - want) > 0.35) a.currentTime = want;
      } else if (!a.paused) a.pause();
    }
    const m = music.current;
    if (m) {
      m.volume = Math.min(1, s.music_volume * (narrating ? 0.35 : 1));
      if (isPlaying && t < total) {
        if (m.paused) { m.currentTime = m.duration ? t % m.duration : t; void m.play().catch(() => {}); }
      } else if (!m.paused) m.pause();
    }
  }, [timeline, scenesById, s.narration_enabled, s.music_volume, total]);

  useEffect(() => {
    if (!musicUrl) { music.current?.pause(); music.current = null; return; }
    const m = new Audio(musicUrl);
    m.loop = true;
    music.current = m;
    return () => m.pause();
  }, [musicUrl]);

  useEffect(() => () => { audios.current.forEach((a) => a.pause()); music.current?.pause(); }, []);

  useEffect(() => {
    if (!playing) { syncAudio(tRef.current, false); return; }
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      tRef.current = Math.min(tRef.current + dt, total);
      setTime(tRef.current);
      syncAudio(tRef.current, true);
      if (tRef.current >= total) { setPlaying(false); return; }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, total, setTime, syncAudio]);

  useEffect(() => { if (!playing) tRef.current = time; }, [time, playing]);

  const toggle = () => {
    if (!playing && tRef.current >= total - 0.05) { tRef.current = 0; setTime(0); }
    setPlaying((p) => !p);
  };

  const m = Math.min(size.w, size.h);
  const vertical = h > w;
  const pal = s.palette;
  const layers: { sc: Scene; ts: Timeline["scenes"][number]; opacity: number }[] = [];
  if (timeline) {
    timeline.scenes.forEach((ts) => {
      const sc = scenesById.get(ts.id);
      if (!sc || time < ts.start || time >= ts.start + ts.duration) return;
      const fadeOutStart = ts.start + ts.duration - ts.trans_out;
      const opacity = time > fadeOutStart && ts.trans_out > 0.05 ? 1 - (time - fadeOutStart) / ts.trans_out : 1;
      layers.push({ sc, ts, opacity });
    });
  }
  const inEnd = timeline?.end_card_start != null && time >= timeline.end_card_start;
  const capScene = layers[layers.length - 1];
  const caption = capScene?.ts.captions.find((c) => time >= c.start && time < c.end);
  const titleFont = s.font;
  const company = project.company;

  return (
    <div className="flex h-full flex-col gap-3">
      <div ref={wrapRef} className="relative flex min-h-0 flex-1 items-center justify-center">
        <div ref={boxRef} className="relative overflow-hidden rounded-lg bg-black shadow-2xl shadow-black/60 ring-1 ring-line" style={{ width: size.w, height: size.h }}>
          {!project.scenes.length && <div className="flex size-full items-center justify-center p-6 text-center text-sm text-muted">Adicione cenas para visualizar</div>}
          {inEnd && (
            <div className="absolute inset-0" style={{ background: `radial-gradient(circle at 70% 20%, ${pal[2]}55, transparent 50%), linear-gradient(160deg, ${pal[0]}, ${pal[1]})` }}>
              {project.logo && <img src={project.logo.url} alt="" className="absolute left-1/2 -translate-x-1/2 rounded-xl bg-white/90 p-[2%]" style={{ top: vertical ? "12%" : "8%", width: m * 0.3 }} />}
              <div className="absolute inset-x-0 flex flex-col items-center gap-[1.2%] px-[8%] text-center" style={{ top: project.logo ? "44%" : "38%", ...textStyle("slide_up", time - (timeline!.end_card_start ?? 0) - 0.3) }}>
                {s.end_card.headline && <p className="font-extrabold" style={{ color: pal[2], fontSize: m * 0.0575 }}>{s.end_card.headline}</p>}
                <p className="font-bold leading-tight" style={{ fontFamily: titleFont, fontSize: m * 0.1, color: pal[3], textTransform: UPPER.has(titleFont) ? "uppercase" : undefined }}>{company.name}</p>
                {s.end_card.show_phone && (company.whatsapp || company.phone) && <p className="bg-black/50 px-[2%] font-semibold" style={{ fontSize: m * 0.05, color: pal[3] }}>{company.whatsapp ? "WhatsApp " : "Tel. "}{company.whatsapp || company.phone}</p>}
                {s.end_card.show_instagram && company.instagram && <p className="bg-black/50 px-[2%] font-semibold" style={{ fontSize: m * 0.05, color: pal[3] }}>@{company.instagram.replace(/^@/, "")}</p>}
                {s.end_card.show_address && company.address && <p className="bg-black/50 px-[2%] font-semibold" style={{ fontSize: m * 0.05, color: pal[3] }}>{company.address}</p>}
              </div>
            </div>
          )}
          {layers.map(({ sc, ts, opacity }) => {
            const p = (time - ts.start) / ts.duration;
            const local = time - ts.start - (ts.start === 0 ? 0.15 : 0.25);
            const bg = sc.image?.url;
            return (
              <div key={sc.id} className="absolute inset-0" style={{ opacity }}>
                {bg ? (
                  sc.fit === "contain_blur" ? (
                    <>
                      <img src={bg} alt="" className="absolute inset-0 size-full scale-110 object-cover blur-xl brightness-50" />
                      <img src={bg} alt="" className="absolute inset-[8%] size-[84%] object-contain drop-shadow-2xl" style={{ transform: motionTransform(sc.motion, p) }} />
                    </>
                  ) : <img src={bg} alt="" className="absolute inset-0 size-full object-cover" style={{ transform: motionTransform(sc.motion, p) }} />
                ) : <div className="absolute inset-0" style={{ background: `linear-gradient(160deg, ${pal[0]}, ${pal[1]})` }} />}
                <div className="pointer-events-none absolute inset-0" style={{ background: "linear-gradient(to bottom, rgba(0,0,0,.35), transparent 30%, transparent 55%, rgba(0,0,0,.6))" }} />
                {local > 0 && (sc.title || sc.subtitle) && (
                  <div className="absolute inset-x-[8%] flex -translate-y-1/2 flex-col items-center gap-[0.6em] text-center" style={{ top: `${titleTop(sc.text_position, vertical)}%`, ...textStyle(sc.text_animation, local) }}>
                    {sc.title && <TitleView text={sc.title} role={sc.role} style={s.style} font={titleFont} m={m} pal={pal} local={local} />}
                    {sc.subtitle && <p className={clsx("font-semibold", ["moderno", "profissional", "tecnologico"].includes(s.style) && "rounded bg-black/45 px-[0.5em] py-[0.15em]")} style={{ fontSize: m * 0.052, color: ["moderno", "profissional", "tecnologico"].includes(s.style) ? pal[3] : pal[2], textShadow: "0 2px 6px rgba(0,0,0,.7)" }}>{sc.subtitle}</p>}
                  </div>
                )}
              </div>
            );
          })}
          {caption && s.subtitles_enabled && (
            <div className="absolute inset-x-[8%] flex justify-center text-center" style={{ bottom: "10%" }}>
              <span className={clsx("font-extrabold leading-snug", s.subtitle_style === "boxed" && "rounded-md px-[0.4em] py-[0.1em]")}
                style={{ fontSize: m * 0.06, color: s.subtitle_style === "highlight" ? pal[2] : pal[3], background: s.subtitle_style === "boxed" ? `${pal[0]}C0` : undefined,
                  textShadow: s.subtitle_style === "boxed" ? undefined : `0 0 ${s.subtitle_style === "bold_outline" ? 6 : 3}px #000, 0 2px 4px #000` }}>{caption.text}</span>
            </div>
          )}
          {s.watermark.enabled && (
            <div className={clsx("absolute", s.watermark.position.includes("top") ? "top-[4%]" : "bottom-[4%]", s.watermark.position.includes("left") ? "left-[4%]" : "right-[4%]")} style={{ opacity: s.watermark.opacity }}>
              {s.watermark.type === "image" && project.logo ? <img src={project.logo.url} alt="" style={{ width: m * 0.16 }} />
                : <span className="font-semibold text-white" style={{ fontSize: m * 0.032, textShadow: "0 1px 3px #000" }}>{s.watermark.text || company.name}</span>}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 px-1">
        <button onClick={toggle} aria-label={playing ? "Pausar" : "Reproduzir"} className="ember-gradient flex size-9 shrink-0 items-center justify-center rounded-full text-black">
          {playing ? <Pause className="size-4" /> : <Play className="ml-0.5 size-4" />}
        </button>
        <button onClick={() => { setPlaying(false); tRef.current = 0; setTime(0); }} aria-label="Reiniciar" className="text-muted hover:text-fg"><RotateCcw className="size-4" /></button>
        <input type="range" aria-label="Posição" min={0} max={total || 1} step={0.01} value={Math.min(time, total)} className="flex-1 accent-[var(--color-ember)]"
          onChange={(e) => {
            const t = Number(e.target.value);
            tRef.current = t; setTime(t); syncAudio(t, playing);
            const ts = timeline?.scenes.find((x) => t >= x.start && t < x.start + x.duration);
            if (ts) onSelect(ts.id);
          }} />
        <span className="w-24 text-right text-xs tabular-nums text-muted">{fmtSec(time)} / {fmtSec(total)}</span>
      </div>
    </div>
  );
}
