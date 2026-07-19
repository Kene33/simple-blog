export function Brand({ compact = false }) {
  return <div className="brand" aria-label="Simple">
    <span className="brand-mark">S</span>
    {!compact && <span>Simple</span>}
  </div>;
}
