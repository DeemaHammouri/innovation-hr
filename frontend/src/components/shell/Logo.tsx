/** The "IA" mark: a blue square with white letters. */
export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className="inline-flex shrink-0 items-center justify-center rounded-control bg-primary-strong text-label font-bold text-white"
    >
      <span dir="ltr">IA</span>
    </span>
  );
}
