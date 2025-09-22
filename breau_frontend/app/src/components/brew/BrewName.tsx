// src/components/brew/BrewName.tsx
import { useId } from "react";

export default function BrewName({
  value,
  onChange,
  placeholder = "e.g., Las Flores — 1:15 Floral Focus",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <label className="col" htmlFor={id}>
      <span>Brew name</span>
      <input
        id={id}
        className="input"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="hint">Shown in History and on the Profile header.</div>
    </label>
  );
}
