import { useQuery } from "@tanstack/react-query";

import { listProjects } from "./api";

export const projectQueryKey = ["projects"] as const;

export function useProjects(enabled: boolean) {
  return useQuery({
    queryKey: projectQueryKey,
    queryFn: listProjects,
    enabled,
  });
}
