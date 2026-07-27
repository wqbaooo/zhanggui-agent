import { notFound } from "next/navigation";
import { FinancePage, type FinanceView } from "@/components/finance/FinancePage";

const SECTIONS = new Set<FinanceView>(["workspace", "intelligence", "ledger", "funds", "profit", "reports"]);

export default async function FinanceSectionPage({
  params,
  searchParams,
}: {
  params: Promise<{ section: string }>;
  searchParams: Promise<{ date?: string }>;
}) {
  const { section } = await params;
  const { date = "" } = await searchParams;
  if (!SECTIONS.has(section as FinanceView)) notFound();
  return <FinancePage initialView={section as FinanceView} initialDate={date} />;
}
