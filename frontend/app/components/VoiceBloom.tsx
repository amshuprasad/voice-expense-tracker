"use client";

import { useEffect, useRef } from "react";

type Props = {
    text?: string;
    /** Live mic level, 0..1. Louder voice = more agitation and brighter letters. */
    level?: number;
    /** Particle + link colour. */
    accent?: string;
    /** Colour the letters light up in. */
    ink?: string;
    fontFamily?: string;
    fontWeight?: number;
    /** 0.6 (sparse) .. 1.6 (dense). */
    density?: number;
    height?: number | string;
    className?: string;
};

type Particle = {
    x: number;
    y: number;
    vx: number;
    vy: number;
    t: number; // target index, -1 = searching
    hold: number; // seconds left in current state
};

function hexToRgb(hex: string): [number, number, number] {
    const h = hex.replace("#", "");
    const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
    const n = parseInt(full, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function makeSprite(rgb: [number, number, number]) {
    const s = 64;
    const c = document.createElement("canvas");
    c.width = c.height = s;
    const g = c.getContext("2d")!;
    const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    grad.addColorStop(0, `rgba(${rgb.join(",")},1)`);
    grad.addColorStop(1, `rgba(${rgb.join(",")},0)`);
    g.fillStyle = grad;
    g.fillRect(0, 0, s, s);
    return c;
}

const LINK_DIST = 22;
const MAX_LINKS = 3;

export default function VoiceBloom({
    text = "VoiceSpend",
    level = 0,
    accent = "#ff5c75",
    ink = "#ffe9ec",
    fontFamily = "system-ui, -apple-system, 'Segoe UI', sans-serif",
    fontWeight = 800,
    density = 1,
    height = 220,
    className,
}: Props) {
    const wrapRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const levelRef = useRef(0);
    levelRef.current = Math.max(0, Math.min(1, level));

    useEffect(() => {
        const wrap = wrapRef.current!;
        const canvas = canvasRef.current!;
        const ctx = canvas.getContext("2d")!;

        const light = document.createElement("canvas");
        const lctx = light.getContext("2d")!;
        const mask = document.createElement("canvas");
        const mctx = mask.getContext("2d", { willReadFrequently: true })!;

        const accentRgb = hexToRgb(accent);
        const sprite = makeSprite(hexToRgb(ink));
        const reduceMotion = window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        ).matches;

        let w = 1;
        let h = 1;
        let dpr = 1;
        let targets: { x: number; y: number }[] = [];
        const parts: Particle[] = [];
        let head = new Int32Array(1);
        let next = new Int32Array(1);
        let cols = 1;
        let rows = 1;

        let raf = 0;
        let last = performance.now();
        let time = 0;
        let visible = true;
        const pointer = { x: -999, y: -999 };

        const pickTarget = () =>
            targets.length ? Math.floor(Math.random() * targets.length) : -1;

        function build() {
            const rect = wrap.getBoundingClientRect();
            w = Math.max(1, Math.floor(rect.width));
            h = Math.max(1, Math.floor(rect.height));
            dpr = Math.min(window.devicePixelRatio || 1, 2);

            for (const c of [canvas, light, mask]) {
                c.width = Math.floor(w * dpr);
                c.height = Math.floor(h * dpr);
            }
            for (const c of [ctx, lctx, mctx]) c.setTransform(dpr, 0, 0, dpr, 0, 0);

            // Draw the wordmark once into an offscreen mask, fitted to the width.
            const fontOf = (s: number) => `${fontWeight} ${s}px ${fontFamily}`;
            const lines = text.split("\n");
            const lineGap = 1.05;
            let size = Math.min(h * 0.62, (h * 0.86) / (lines.length * lineGap));
            mctx.font = fontOf(size);
            const measured = Math.max(
                ...lines.map((l) => mctx.measureText(l).width)
            );
            const maxW = w * 0.92;
            if (measured > maxW) size *= maxW / measured;
            mctx.font = fontOf(size);
            mctx.textAlign = "center";
            mctx.textBaseline = "middle";
            mctx.fillStyle = ink;
            mctx.clearRect(0, 0, w, h);
            lines.forEach((line, i) => {
                const y = h / 2 + (i - (lines.length - 1) / 2) * size * lineGap;
                mctx.fillText(line, w / 2, y);
            });

            // Sample letter pixels as attraction targets.
            const img = mctx.getImageData(0, 0, mask.width, mask.height).data;
            const gap = Math.max(3, Math.round(size / (22 * density)));
            const step = Math.max(1, Math.round(gap * dpr));
            targets = [];
            for (let y = 0; y < mask.height; y += step) {
                for (let x = 0; x < mask.width; x += step) {
                    if (img[(y * mask.width + x) * 4 + 3] > 128) {
                        targets.push({ x: x / dpr, y: y / dpr });
                    }
                }
            }

            const count = Math.min(
                1100,
                Math.max(150, Math.round(targets.length * 0.5))
            );
            while (parts.length < count) {
                parts.push({
                    x: Math.random() * w,
                    y: Math.random() * h,
                    vx: 0,
                    vy: 0,
                    t: -1,
                    hold: 0,
                });
            }
            parts.length = count;
            for (const p of parts) {
                p.t = pickTarget();
                p.hold = 1.5 + Math.random() * 5;
            }

            cols = Math.ceil(w / LINK_DIST) + 1;
            rows = Math.ceil(h / LINK_DIST) + 1;
            head = new Int32Array(cols * rows);
            next = new Int32Array(count);

            lctx.clearRect(0, 0, w, h);
        }

        function drawStatic() {
            ctx.clearRect(0, 0, w, h);
            ctx.globalAlpha = 1;
            ctx.drawImage(mask, 0, 0, w, h);
        }

        function frame(now: number) {
            raf = requestAnimationFrame(frame);
            if (!visible) {
                last = now;
                return;
            }
            const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
            last = now;
            const k = dt * 60;
            time += dt;
            const lv = levelRef.current;

            // Fade the light layer, then add glow where particles have landed.
            lctx.globalCompositeOperation = "destination-out";
            lctx.fillStyle = `rgba(0,0,0,${Math.min(1, 0.1 * k)})`;
            lctx.fillRect(0, 0, w, h);
            lctx.globalCompositeOperation = "lighter";

            const glowR = 18 + lv * 16;
            const damp = Math.pow(0.87, k);

            for (let i = 0; i < parts.length; i++) {
                const p = parts[i];
                p.hold -= dt * (1 + lv * 3);

                if (p.t >= 0) {
                    const tg = targets[p.t];
                    const dx = tg.x - p.x;
                    const dy = tg.y - p.y;
                    p.vx += dx * 0.02 * k;
                    p.vy += dy * 0.02 * k;

                    const dist = Math.hypot(dx, dy);
                    if (dist < 22) {
                        lctx.globalAlpha = (1 - dist / 22) * 0.35 * (1 + lv);
                        lctx.drawImage(
                            sprite,
                            p.x - glowR,
                            p.y - glowR,
                            glowR * 2,
                            glowR * 2
                        );
                    }

                    if (p.hold <= 0) {
                        // Let go and go searching.
                        const a = Math.random() * Math.PI * 2;
                        const s = 1.5 + lv * 5;
                        p.vx = Math.cos(a) * s;
                        p.vy = Math.sin(a) * s;
                        p.t = -1;
                        p.hold = 0.5 + Math.random() * 1.2;
                    }
                } else {
                    const a =
                        (Math.sin(p.x * 0.008 + time * 0.7) +
                            Math.cos(p.y * 0.009 - time * 0.6)) *
                        Math.PI;
                    p.vx += Math.cos(a) * 0.22 * k;
                    p.vy += Math.sin(a) * 0.22 * k;

                    if (p.x < 0 || p.x > w) p.vx -= Math.sign(p.x - w / 2) * 0.3 * k;
                    if (p.y < 0 || p.y > h) p.vy -= Math.sign(p.y - h / 2) * 0.3 * k;

                    if (p.hold <= 0) {
                        // Reconnect to a new part of the word.
                        p.t = pickTarget();
                        p.hold = 2 + Math.random() * 4;
                    }
                }

                if (lv > 0.02) {
                    p.vx += (Math.random() - 0.5) * lv * 1.2 * k;
                    p.vy += (Math.random() - 0.5) * lv * 1.2 * k;
                }

                const pdx = p.x - pointer.x;
                const pdy = p.y - pointer.y;
                const pd = Math.hypot(pdx, pdy);
                if (pd < 80 && pd > 0.01) {
                    const f = (1 - pd / 80) * 1.6 * k;
                    p.vx += (pdx / pd) * f;
                    p.vy += (pdy / pd) * f;
                }

                p.vx *= damp;
                p.vy *= damp;
                p.x += p.vx * k;
                p.y += p.vy * k;
            }

            // Keep the glow only where letters are.
            lctx.globalAlpha = 1;
            lctx.globalCompositeOperation = "destination-in";
            lctx.drawImage(mask, 0, 0, w, h);
            lctx.globalCompositeOperation = "source-over";

            // Compose: dim wordmark, lit wordmark, links, particles.
            ctx.clearRect(0, 0, w, h);
            ctx.globalAlpha = 0.09;
            ctx.drawImage(mask, 0, 0, w, h);
            ctx.globalAlpha = 1;
            ctx.drawImage(light, 0, 0, w, h);

            head.fill(-1);
            for (let i = 0; i < parts.length; i++) {
                const cx = (parts[i].x / LINK_DIST) | 0;
                const cy = (parts[i].y / LINK_DIST) | 0;
                if (cx < 0 || cy < 0 || cx >= cols || cy >= rows) {
                    next[i] = -1;
                    continue;
                }
                const idx = cy * cols + cx;
                next[i] = head[idx];
                head[idx] = i;
            }

            ctx.strokeStyle = `rgba(${accentRgb.join(",")},${0.2 + lv * 0.25})`;
            ctx.lineWidth = 0.7;
            ctx.beginPath();
            const L2 = LINK_DIST * LINK_DIST;
            for (let i = 0; i < parts.length; i++) {
                const a = parts[i];
                const cx = (a.x / LINK_DIST) | 0;
                const cy = (a.y / LINK_DIST) | 0;
                if (cx < 0 || cy < 0 || cx >= cols || cy >= rows) continue;
                let links = 0;
                for (let oy = -1; oy <= 1 && links < MAX_LINKS; oy++) {
                    for (let ox = -1; ox <= 1 && links < MAX_LINKS; ox++) {
                        const nx = cx + ox;
                        const ny = cy + oy;
                        if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
                        let j = head[ny * cols + nx];
                        while (j !== -1 && links < MAX_LINKS) {
                            if (j > i) {
                                const b = parts[j];
                                const dx = a.x - b.x;
                                const dy = a.y - b.y;
                                if (dx * dx + dy * dy < L2) {
                                    ctx.moveTo(a.x, a.y);
                                    ctx.lineTo(b.x, b.y);
                                    links++;
                                }
                            }
                            j = next[j];
                        }
                    }
                }
            }
            ctx.stroke();

            ctx.fillStyle = `rgb(${accentRgb.join(",")})`;
            for (let i = 0; i < parts.length; i++) {
                const p = parts[i];
                const s = p.t < 0 ? 2.4 : 1.8;
                ctx.fillRect(p.x - s / 2, p.y - s / 2, s, s);
            }
        }

        build();

        if (reduceMotion) {
            drawStatic();
        } else {
            raf = requestAnimationFrame(frame);
        }

        const ro = new ResizeObserver(() => {
            build();
            if (reduceMotion) drawStatic();
        });
        ro.observe(wrap);

        const io = new IntersectionObserver(([entry]) => {
            visible = entry.isIntersecting;
        });
        io.observe(wrap);

        const onMove = (e: PointerEvent) => {
            const r = wrap.getBoundingClientRect();
            pointer.x = e.clientX - r.left;
            pointer.y = e.clientY - r.top;
        };
        const onLeave = () => {
            pointer.x = pointer.y = -999;
        };
        wrap.addEventListener("pointermove", onMove);
        wrap.addEventListener("pointerleave", onLeave);

        // Rebuild once webfonts are ready so the letter shapes are correct.
        document.fonts?.ready.then(() => {
            build();
            if (reduceMotion) drawStatic();
        });

        return () => {
            cancelAnimationFrame(raf);
            ro.disconnect();
            io.disconnect();
            wrap.removeEventListener("pointermove", onMove);
            wrap.removeEventListener("pointerleave", onLeave);
        };
    }, [text, accent, ink, fontFamily, fontWeight, density]);

    return (
        <div
            ref={wrapRef}
            className={className}
            role="img"
            aria-label={text.replace(/\n/g, " ")}
            style={{ position: "relative", width: "100%", height, touchAction: "pan-y" }}
        >
            <canvas
                ref={canvasRef}
                aria-hidden="true"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
            />
        </div>
    );
}