import type {
  Campaign,
  ICPFilters,
  Lead,
  OutreachMessage,
  PipelineStats,
  PipelineStatus,
} from "./types";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "/leadgen";
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || `${BASE_PATH}`;
// API key is injected server-side by the proxy route — never expose to browser
const API_KEY = "";

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  const res = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export const campaignsApi = {
  list: () => request<Campaign[]>("/api/campaigns"),

  get: (id: string) => request<Campaign>(`/api/campaigns/${id}`),

  create: (data: {
    name: string;
    description?: string;
    icp_raw_text?: string;
    parsed_filters?: string;
    target_titles?: string;
    target_industries?: string;
    target_seniority?: string;
    target_locations?: string;
    min_employees?: number;
    max_employees?: number;
    keywords?: string;
  }) =>
    request<Campaign>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  createFromICP: (data: {
    name: string;
    icp_text: string;
    auto_run?: boolean;
    enrich_top_n?: number;
    min_score_for_enrichment?: number;
  }) =>
    request<Campaign>("/api/campaigns/create-from-icp", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  parseICP: (icp_text: string) =>
    request<ICPFilters>("/api/campaigns/parse-icp", {
      method: "POST",
      body: JSON.stringify({ icp_text }),
    }),

  runPipeline: (data: {
    campaign_id: string;
    enrich_top_n?: number;
    min_score_for_enrichment?: number;
  }) =>
    request<{ status: string; campaign_id: string; pipeline_stage: string }>(
      "/api/campaigns/run-pipeline",
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  getPipelineStatus: (id: string) =>
    request<PipelineStatus>(`/api/campaigns/${id}/pipeline-status`),

  resetPipeline: (id: string) =>
    request<Campaign>(`/api/campaigns/${id}/reset-pipeline`, {
      method: "POST",
    }),

  delete: (id: string) =>
    request<void>(`/api/campaigns/${id}`, { method: "DELETE" }),
};

export const leadsApi = {
  list: (params?: {
    campaign_id?: string;
    status?: string;
    min_score?: number;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.campaign_id) search.set("campaign_id", params.campaign_id);
    if (params?.status) search.set("status", params.status);
    if (params?.min_score) search.set("min_score", String(params.min_score));
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.offset) search.set("offset", String(params.offset));
    const qs = search.toString();
    return request<Lead[]>(`/api/leads${qs ? `?${qs}` : ""}`);
  },

  get: (id: string) => request<Lead>(`/api/leads/${id}`),

  update: (id: string, data: { status?: string; score?: number }) =>
    request<Lead>(`/api/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  bulkUpdateStatus: (lead_ids: string[], status: string) =>
    request<Lead[]>("/api/leads/bulk-status", {
      method: "PATCH",
      body: JSON.stringify({ lead_ids, status }),
    }),

  stats: () => request<PipelineStats>("/api/leads/stats"),
};

export const outreachApi = {
  list: (params?: { lead_id?: string; campaign_id?: string; status?: string }) => {
    const search = new URLSearchParams();
    if (params?.lead_id) search.set("lead_id", params.lead_id);
    if (params?.campaign_id) search.set("campaign_id", params.campaign_id);
    if (params?.status) search.set("status", params.status);
    return request<OutreachMessage[]>(
      `/api/outreach${search.toString() ? `?${search.toString()}` : ""}`,
    );
  },

  update: (id: string, data: { subject?: string; body?: string }) =>
    request<OutreachMessage>(`/api/outreach/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  generate: (data: {
    lead_ids: string[];
    channel?: string;
    tone?: string;
    custom_instructions?: string;
  }) =>
    request<{ messages: OutreachMessage[] }>("/api/outreach/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  send: (message_ids: string[]) =>
    request<{ sent: number; failed: number }>("/api/outreach/send", {
      method: "POST",
      body: JSON.stringify({ message_ids }),
    }),
};

export function getExportUrl(
  campaignId: string,
  minScore = 0,
): string {
  return `${BASE_PATH}/api/campaigns/${campaignId}/export?min_score=${minScore}`;
}
