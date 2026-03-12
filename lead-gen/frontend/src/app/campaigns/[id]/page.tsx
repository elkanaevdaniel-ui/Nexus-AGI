"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Campaign, PipelineStatus } from "@/lib/types";
import { campaignsApi } from "@/lib/api";
import { PipelineProgress } from "@/components/PipelineProgress";
import { StatusBadge } from "@/components/StatusBadge";

export default function CampaignDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    loadData();
  }, [id]);

  // Poll pipeline status while running (max 120 polls = 10 min)
  useEffect(() => {
    if (!campaign) return;
    const isActive = !["idle", "complete", "failed"].includes(campaign.pipeline_stage);
    if (!isActive) return;

    let polls = 0;
    const interval = setInterval(async () => {
      polls++;
      if (polls > 120) {
        clearInterval(interval);
        // Force refresh to pick up stale detection from backend
        const updated = await campaignsApi.get(id);
        setCampaign(updated);
        return;
      }
      try {
        const status = await campaignsApi.getPipelineStatus(id);
        setPipelineStatus(status);
        if (["complete", "failed"].includes(status.pipeline_stage)) {
          const updated = await campaignsApi.get(id);
          setCampaign(updated);
          clearInterval(interval);
        }
      } catch {
        // ignore polling errors
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [campaign?.pipeline_stage, id]);

  async function loadData() {
    try {
      const [c, ps] = await Promise.all([
        campaignsApi.get(id),
        campaignsApi.getPipelineStatus(id),
      ]);
      setCampaign(c);
      setPipelineStatus(ps);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load campaign");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunPipeline() {
    setRunning(true);
    setError(null);
    try {
      // Reset stuck/failed pipelines first, then run
      if (campaign && ["failed", "searching", "scoring", "enriching", "drafting"].includes(campaign.pipeline_stage)) {
        await campaignsApi.resetPipeline(id);
      }
      await campaignsApi.runPipeline({ campaign_id: id });
      const updated = await campaignsApi.get(id);
      setCampaign(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start pipeline");
    } finally {
      setRunning(false);
    }
  }

  async function handleResetPipeline() {
    setRunning(true);
    setError(null);
    try {
      const updated = await campaignsApi.resetPipeline(id);
      setCampaign(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to reset pipeline");
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <p className="text-sm text-muted">Loading...</p>;
  if (!campaign && error) return <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>;
  if (!campaign) return null;

  const isFailed = campaign.pipeline_stage === "failed";
  const isStuck = !["idle", "complete", "failed"].includes(campaign.pipeline_stage);
  const canRun = !isStuck || isFailed;

  return (
    <div>
      <div className="flex items-center gap-2 text-sm text-muted mb-4">
        <Link href="/" className="hover:text-foreground">Campaigns</Link>
        <span>/</span>
        <span className="text-foreground">{campaign.name}</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-foreground">{campaign.name}</h1>
          <StatusBadge status={campaign.status} size="md" />
        </div>
        <div className="flex items-center gap-2">
          {isStuck && (
            <button
              onClick={handleResetPipeline}
              disabled={running}
              className="px-4 py-2 border border-orange-300 text-orange-600 text-sm font-medium rounded-lg hover:bg-orange-50 disabled:opacity-50 transition-colors"
            >
              {running ? "Resetting..." : "Reset Pipeline"}
            </button>
          )}
          {canRun && (
            <button
              onClick={handleRunPipeline}
              disabled={running}
              className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              {running ? "Starting..." : isFailed ? "Retry Pipeline" : "Run Pipeline"}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-red-700">{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 text-sm ml-2">Dismiss</button>
        </div>
      )}

      {/* Pipeline Progress */}
      <div className="bg-white border border-border rounded-lg p-5 mb-6">
        <h3 className="text-sm font-medium text-foreground mb-3">Pipeline Progress</h3>
        <PipelineProgress currentStage={pipelineStatus?.pipeline_stage || campaign.pipeline_stage} />

        {pipelineStatus && (
          <div className="grid grid-cols-4 gap-4 mt-4">
            <StatCard label="Total Leads" value={pipelineStatus.total_leads} />
            <StatCard label="Scored" value={pipelineStatus.scored_leads} />
            <StatCard label="Enriched" value={pipelineStatus.enriched_leads} />
            <StatCard label="Drafts" value={pipelineStatus.drafts_generated} />
          </div>
        )}
      </div>

      {/* ICP */}
      {campaign.icp_raw_text && (
        <div className="bg-white border border-border rounded-lg p-5 mb-6">
          <h3 className="text-sm font-medium text-foreground mb-2">ICP Description</h3>
          <p className="text-sm text-muted">{campaign.icp_raw_text}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <Link
          href={`/campaigns/${id}/prospects`}
          className="px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-gray-50 transition-colors"
        >
          View Prospects
        </Link>
        <Link
          href={`/campaigns/${id}/drafts`}
          className="px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-gray-50 transition-colors"
        >
          View Drafts
        </Link>
        <Link
          href={`/campaigns/${id}/export`}
          className="px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-gray-50 transition-colors"
        >
          Export CSV
        </Link>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <p className="text-2xl font-semibold text-foreground">{value}</p>
      <p className="text-xs text-muted mt-0.5">{label}</p>
    </div>
  );
}
