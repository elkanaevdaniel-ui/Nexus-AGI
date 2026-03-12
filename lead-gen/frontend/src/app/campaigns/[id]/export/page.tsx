"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Campaign } from "@/lib/types";
import { campaignsApi, getExportUrl } from "@/lib/api";

export default function ExportPage() {
  const params = useParams();
  const id = params.id as string;
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [minScore, setMinScore] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    campaignsApi
      .get(id)
      .then(setCampaign)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-sm text-muted">Loading...</p>;
  if (!campaign) return null;

  const exportUrl = getExportUrl(id, minScore);

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-2 text-sm text-muted mb-4">
        <Link href="/" className="hover:text-foreground">Campaigns</Link>
        <span>/</span>
        <Link href={`/campaigns/${id}`} className="hover:text-foreground">{campaign.name}</Link>
        <span>/</span>
        <span className="text-foreground">Export</span>
      </div>

      <h1 className="text-xl font-semibold text-foreground mb-6">Export</h1>

      <div className="bg-white border border-border rounded-lg p-5">
        <p className="text-sm text-muted mb-4">
          Export {campaign.total_leads} leads from &ldquo;{campaign.name}&rdquo;
        </p>

        <div className="mb-6">
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Minimum Score
          </label>
          <input
            type="number"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value) || 0)}
            min={0}
            max={100}
            className="w-28 px-3 py-2 border border-border rounded-lg text-sm"
          />
          <p className="text-xs text-muted mt-1">Only export leads with score at or above this value</p>
        </div>

        <a
          href={exportUrl}
          download
          className="inline-flex items-center px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-blue-600 transition-colors"
        >
          Download CSV
        </a>
      </div>
    </div>
  );
}
