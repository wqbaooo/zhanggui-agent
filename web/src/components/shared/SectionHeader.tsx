export function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800" style={{ fontFamily: "Antonio, sans-serif" }}>{title}</h2>
      <p className="text-[10px] text-gray-400 font-medium mt-0.5">{subtitle}</p>
    </div>
  );
}
