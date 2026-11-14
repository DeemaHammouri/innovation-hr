/** Keeps emails, phone numbers and passwords in left-to-right order inside right-to-left text. */
export function Ltr({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <bdi dir="ltr" className={`inline-block max-w-full align-bottom ${className}`}>
      {children}
    </bdi>
  );
}
