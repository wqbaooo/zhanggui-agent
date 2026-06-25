import { useQuery } from "@tanstack/react-query";
import { apiGet, DEFAULT_PROJECT_ID, type DailyOperationEntry, type ProjectCockpit, type OperationListResponse } from "@/lib/api";
import type { OperationDailyRecord } from "@/domain/types";
import {
  mockProject, mockInvestment, mockLocation, mockOperations,
  mockMenuItems, mockRisks, mockPermissions,
  mockFulfillment, mockActions, mockPlatformMetrics, mockDeliveryFunnel, mockPlatformComparison,
} from "@/data/mockProject";

const PROJECT_ID = DEFAULT_PROJECT_ID;

export function useProjectData() {
  const cockpitQuery = useQuery({
    queryKey: ["cockpit", PROJECT_ID],
    queryFn: () => apiGet<ProjectCockpit>(`/api/projects/${PROJECT_ID}/cockpit?days=7`),
    enabled: !!PROJECT_ID,
    retry: 1,
    staleTime: 30_000,
  });

  const opsQuery = useQuery({
    queryKey: ["operations", PROJECT_ID],
    queryFn: () => apiGet<OperationListResponse>(`/api/projects/${PROJECT_ID}/operations?days=30`),
    enabled: !!PROJECT_ID,
    retry: 1,
    staleTime: 30_000,
  });

  const cockpit = cockpitQuery.data;
  const opsData = opsQuery.data;
  const hasApiData = cockpit && (cockpit.operations?.entry_count ?? 0) > 0;
  const operationRecords = (opsData?.entries ?? []).map(mapDailyOperation);
  const hasRealOps = hasApiData && (cockpit?.operations?.entry_count ?? 0) > 0;

  return {
    isLoading: cockpitQuery.isLoading || opsQuery.isLoading,
    isApiConnected: !!cockpit,

    project: mockProject,

    cockpit: hasApiData ? cockpit : null,

    investment: mockInvestment,
    location: mockLocation,

      operations: hasRealOps ? operationRecords : mockOperations,

    hasRealOperations: hasRealOps,

    menuItems: mockMenuItems,
    risks: mockRisks,
    permissions: mockPermissions,
    fulfillment: mockFulfillment,
    actions: mockActions,

    platformMetrics: mockPlatformMetrics,
    deliveryFunnel: mockDeliveryFunnel,
    platformComparison: mockPlatformComparison,
  };
}

function mapDailyOperation(entry: DailyOperationEntry): OperationDailyRecord {
  const deliveryOrders = entry.takeout_orders ?? 0;
  const dineInOrders = Math.max((entry.orders ?? 0) - deliveryOrders, 0);
  const deliveryRatio = entry.orders > 0 ? deliveryOrders / entry.orders : 0;
  const deliveryRevenue = Math.round((entry.revenue ?? 0) * deliveryRatio * 100) / 100;
  const dineInRevenue = Math.max((entry.revenue ?? 0) - deliveryRevenue, 0);

  return {
    date: entry.date,
    revenue: entry.revenue ?? 0,
    orders: entry.orders ?? 0,
    averageOrderValue: entry.orders > 0 ? (entry.revenue ?? 0) / entry.orders : 0,
    dineInOrders,
    deliveryOrders,
    dineInRevenue,
    deliveryRevenue,
    materialCost: entry.food_cost ?? 0,
    packagingCost: 0,
    platformCommission: entry.platform_fee ?? 0,
    deliverySubsidy: 0,
    discountCost: entry.marketing_cost ?? 0,
    laborCost: entry.labor ?? 0,
    rentAllocated: entry.rent_allocated ?? 0,
    utilitiesAllocated: entry.utility ?? 0,
    marketingCost: entry.marketing_cost ?? 0,
    lossAmount: entry.inventory_loss ?? 0,
    badReviews: entry.bad_reviews ?? 0,
    newMembers: 0,
    repeatOrders: 0,
    notes: entry.notes ?? "",
  };
}
