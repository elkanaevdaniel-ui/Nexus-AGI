"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Campaign, PipelineStats } from "@/lib/types";
import { campaignsApi, leadsApi } from "@/lib/api";
import { CampaignCard } from "@/components/CampaignCard";
import { EmptyState } from "@/components/EmptyState";

export default function DashboardPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      campaignsApi.list(),
      leadsApi.stats().catch(() => null),
    ])
      .then(([c, s]) => {
        setCampaigns(c);
        setStats(s);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-xl font-semibold text-foreground">Campaigns</h1>
        <Link
          href="/campaigns/new"
          className="inline-flex items-center px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-blue-600 transition-colors"
        >
          + New Campaign
        </Link>
      </div>

      {/* Stats Overview */}
      {stats && stats.total_leads > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatTile label="Total Leads" value={stats.total_leads} />
          <StatTile label="Scored" value={stats.scored} />
          <StatTile label="Enriched" value={stats.enriched} />
          <StatTile label="Contacted" value={stats.contacted} />
          <StatTile label="Qualified" value={stats.qualified} accent="green" />
          <StatTile label="Converted" value={stats.converted} accent="green" />
          <StatTile label="Avg Score" value={Math.round(stats.avg_score)} />
          <StatTile
            label="Pipeline Value"
            value={`$${stats.total_deals_value.toLocaleString()}`}
            accent="blue"
          />
        </div>
      )}

      {loading && <p className="text-sm text-muted">Loading campaigns...</p>}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && campaigns.length === 0 && (
        <EmptyState
          title="No campaigns yet"
          description="Create your first campaign to start finding leads."
          action={{ label: "+ New Campaign", href: "/campaigns/new" }}
        />
      )}

      {!loading && campaigns.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {campaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              onDelete={async (id) => {
                try {
                  await campaignsApi.delete(id);
                  setCampaigns((prev) => prev.filter((c) => c.id !== id));
                } catch (e: unknown) {
                  const msg = e instanceof Error ? e.message : "Delete failed";
                  setError(msg);
                }
              }}
              onRetry={async (id) => {
                try {
                  await campaignsApi.resetPipeline(id);
                  await campaignsApi.runPipeline({ campaign_id: id });
                  const updated = await campaignsApi.list();
                  setCampaigns(updated);
                } catch (e: unknown) {
                  const msg = e instanceof Error ? e.message : "Retry failed";
                  setError(msg);
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function StatTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: "green" | "blue";
}) {
  const valueColor =
    accent === "green"
      ? "text-green-600"
      : accent === "blue"
        ? "text-blue-600"
        : "text-foreground";

  return (
    <div className="bg-white border border-border rounded-lg p-4">
      <p className={`text-2xl font-semibold ${valueColor}`}>{value}</p>
      <p className="text-xs text-muted mt-1">{label}</p>
    </div>
  );
}
