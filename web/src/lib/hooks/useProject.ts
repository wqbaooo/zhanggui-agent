import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, type ProjectCockpit, type DailyOperationEntry } from "@/lib/api";

export function useProject(projectId: string) {
  return useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiGet<ProjectCockpit>(`/api/projects/${projectId}/cockpit?days=7`),
    enabled: !!projectId,
    retry: false,
  });
}

export function useOperations(projectId: string, days = 7) {
  return useQuery({
    queryKey: ["operations", projectId, days],
    queryFn: () => apiGet<{ entries: DailyOperationEntry[]; summary: Record<string, unknown> }>(
      `/api/projects/${projectId}/operations?days=${days}`
    ),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { projectId: string; profile: Record<string, unknown> }) =>
      apiPost(`/api/projects/${data.projectId}/profile`, { profile: data.profile }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project"] }),
  });
}

export function useAddOperation(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entry: Omit<DailyOperationEntry, "id">) =>
      apiPost(`/api/projects/${projectId}/operations`, entry),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["operations", projectId] }),
  });
}
