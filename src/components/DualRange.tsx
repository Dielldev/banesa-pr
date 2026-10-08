interface Props {
  min: number;
  max: number;
  step: number;
  lo: number;
  hi: number;
  onChange: (lo: number, hi: number) => void;
  label: string;
}

export function DualRange({ min, max, step, lo, hi, onChange, label }: Props) {
  const pct = (v: number) => ((v - min) / (max - min)) * 100;
  return (
    <div className="range">
      <div className="range-track" />
      <div className="range-fill" style={{ left: `${pct(lo)}%`, width: `${Math.max(0, pct(hi) - pct(lo))}%` }} />
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={lo}
        aria-label={`Minimum ${label}`}
        onChange={(e) => onChange(Math.min(Number(e.target.value), hi), hi)}
      />
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={hi}
        aria-label={`Maximum ${label}`}
        onChange={(e) => onChange(lo, Math.max(Number(e.target.value), lo))}
      />
    </div>
  );
}
