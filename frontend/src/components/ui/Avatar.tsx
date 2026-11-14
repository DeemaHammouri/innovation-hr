/** First letter of the first and last word of the name. Works for Arabic and Latin names. */
export function initials(fullName: string) {
  const words = fullName.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = Array.from(words[0])[0];
  const last = words.length > 1 ? Array.from(words[words.length - 1])[0] : "";
  return `${first}${last}`.toUpperCase();
}

// One tint per name, always from the blue / navy / teal-gray family (tokens in globals.css).
const TINTS = [
  "bg-avatar-1-bg text-avatar-1-ink",
  "bg-avatar-2-bg text-avatar-2-ink",
  "bg-avatar-3-bg text-avatar-3-ink",
  "bg-avatar-4-bg text-avatar-4-ink",
  "bg-avatar-5-bg text-avatar-5-ink",
  "bg-avatar-6-bg text-avatar-6-ink",
];

function tintFor(name: string) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.codePointAt(0)!) >>> 0;
  return TINTS[hash % TINTS.length];
}

const SIZES = {
  sm: "size-8 text-caption",
  md: "size-10 text-label",
  lg: "size-20 text-title",
};

export function Avatar({ name, size = "md" }: { name: string; size?: keyof typeof SIZES }) {
  return (
    <span aria-hidden className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold ${SIZES[size]} ${tintFor(name)}`}>
      {initials(name)}
    </span>
  );
}
