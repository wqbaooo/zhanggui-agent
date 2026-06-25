export function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-on-background">{title}</h2>
      <p className="mt-1 text-[11px] font-medium text-on-surface-variant">{subtitle}</p>
    </div>
  );
}
