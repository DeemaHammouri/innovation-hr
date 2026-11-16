"use client";

import { Eraser } from "@phosphor-icons/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";

/** A box to draw a signature in with a finger, pen or mouse. Reports a PNG data URL (transparent background), or "" while empty. */
export function SignaturePad({ onChange, label, error }: { onChange: (dataUrl: string) => void; label: string; error?: string }) {
  const { t } = useI18n();
  const ref = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const last = useRef<{ x: number; y: number } | null>(null);
  const [empty, setEmpty] = useState(true);

  const setup = useCallback(() => {
    const c = ref.current;
    if (!c) return;
    const ratio = window.devicePixelRatio || 1;
    const w = c.clientWidth;
    const h = c.clientHeight;
    c.width = Math.round(w * ratio);
    c.height = Math.round(h * ratio);
    const ctx = c.getContext("2d");
    if (ctx) {
      ctx.scale(ratio, ratio);
      ctx.lineWidth = 2.6;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#0a1a5a";
    }
  }, []);

  useEffect(() => {
    setup();
  }, [setup]);

  const point = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  function down(e: React.PointerEvent<HTMLCanvasElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    drawing.current = true;
    last.current = point(e);
    const ctx = e.currentTarget.getContext("2d");
    if (ctx && last.current) {
      ctx.beginPath();
      ctx.arc(last.current.x, last.current.y, 0.8, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  function move(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current || !last.current) return;
    const ctx = e.currentTarget.getContext("2d");
    const p = point(e);
    if (!ctx) return;
    ctx.beginPath();
    ctx.moveTo(last.current.x, last.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last.current = p;
  }

  function up(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return;
    drawing.current = false;
    last.current = null;
    setEmpty(false);
    onChange(e.currentTarget.toDataURL("image/png"));
  }

  function clear() {
    const c = ref.current;
    c?.getContext("2d")?.clearRect(0, 0, c.width, c.height);
    setEmpty(true);
    onChange("");
  }

  return (
    <div>
      <p id="signature-label" className="mb-1.5 text-label text-ink">{label}</p>
      <div className={`relative overflow-hidden rounded-control border bg-surface ${error ? "border-danger" : "border-line"}`}>
        <canvas
          ref={ref}
          role="img"
          aria-labelledby="signature-label"
          className="block h-40 w-full touch-none cursor-crosshair"
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onPointerCancel={up}
        />
        {empty ? <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-label text-ink-3">{t("sign.drawHere")}</span> : null}
      </div>
      <div className="mt-2 flex items-center justify-between gap-3">
        <p role={error ? "alert" : undefined} className={`text-label ${error ? "font-medium text-danger-ink" : "text-ink-2"}`}>{error ?? ""}</p>
        <Button variant="ghost" icon={<Eraser size={18} aria-hidden />} onClick={clear} disabled={empty}>{t("sign.clear")}</Button>
      </div>
    </div>
  );
}
