/** Sets the browser tab title. React hoists <title> into <head> and keeps it right across navigations. */
export function PageTitle({ children }: { children?: string }) {
  return <title>{children ? `${children} · Innovation` : "Innovation"}</title>;
}
