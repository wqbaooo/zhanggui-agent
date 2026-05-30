export function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-700 font-medium">{value}</span>
    </div>
  );
}

export function Clause({ label, value, warn }: { label: string; value: string; warn: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-gray-500">{label}</span>
      <span className={warn ? "text-red-500 font-medium" : "text-gray-700"}>
        {warn && <span className="mr-1">⚠</span>}
        {value}
      </span>
    </div>
  );
}

export function Tag({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-cream-200 bg-white px-2.5 py-1 text-[10px] text-gray-500 font-medium">
      {label}
    </span>
  );
}
