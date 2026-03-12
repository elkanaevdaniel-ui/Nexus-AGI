"use client";

import Link from "next/link";
import { useState } from "react";
import type { Campaign } from "@/lib/types";
import { PipelineProgress } from "./PipelineProgress";
import { StatusBadge } from "./StatusBadge";

const _RUNNING_STAGES = ["searching", "scoring", "enriching", "drafting"];

interface CampaignCardProps {
  campaign: Campaign;
  onDelete?: (id: string) => void;
  onRetry?: (id: string) => void;
}

export function CampaignCard({ campaign, onDelete, onRetry }: CampaignCardProps) {
  const [confirming, setConfirming] = useState(false);
  const [retrying, setRetrying] = useState(false);

  const canRetry = ["failed", "searching", "scoring", "enriching", "drafting"].includes(
    campaign.pipeline_stage,
  );

  function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();

    if (!confirming) {
      setConfirming(true);
      return;
    }

    setActionLoading("delete");
    onDelete?.(campaign.id);
    setConfirming(false);
    setActionLoading(null);
  }

  function handleCancelDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setConfirming(false);
  }

  async function handleRetry(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setActionLoading("retry");
    try {
      await onRetry?.(campaign.id);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReset(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setActionLoading("reset");
    try {
      await onReset?.(campaign.id);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <Link
      href={`/campaigns/${campaign.id}`}
      className="block bg-white border border-border rounded-lg p-5 hover:shadow-sm transition-shadow relative group"
    >
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-medium text-foreground text-sm pr-2">{campaign.name}</h3>
        <StatusBadge status={campaign.status} />
      </div>

      {campaign.icp_raw_text && (
        <p className="text-xs text-muted mb-3 line-clamp-2">{campaign.icp_raw_text}</p>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">
            {campaign.total_leads} lead{campaign.total_leads !== 1 ? "s" : ""}
          </span>
          {canRetry && onRetry && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setRetrying(true);
                onRetry(campaign.id);
              }}
              disabled={retrying}
              className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
            >
              {retrying ? "Retrying..." : "Retry"}
            </button>
          )}
        </div>
        <PipelineProgress currentStage={campaign.pipeline_stage} />
      </div>

      {/* Action buttons row */}
      <div className="flex items-center gap-2 pt-2 border-t border-border">
        {/* Retry button — shown for failed or idle campaigns */}
        {onRetry && (isFailed || isIdle) && (
          <button
            onClick={handleRetry}
            disabled={actionLoading === "retry"}
            className="text-xs px-3 py-1.5 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors disabled:opacity-50 font-medium"
          >
            {actionLoading === "retry" ? "Starting..." : isFailed ? "Retry" : "Run Pipeline"}
          </button>
        )}

        {/* Reset button — shown for stuck (running) campaigns */}
        {onReset && isStuck && (
          <button
            onClick={handleReset}
            disabled={actionLoading === "reset"}
            className="text-xs px-3 py-1.5 bg-orange-500 text-white rounded-md hover:bg-orange-600 transition-colors disabled:opacity-50 font-medium"
          >
            {actionLoading === "reset" ? "Resetting..." : "Reset"}
          </button>
        )}

        <div className="flex-1" />

        {/* Delete button — always visible */}
        {onDelete && !confirming && (
          <button
            onClick={handleDelete}
            className="text-xs px-3 py-1.5 text-red-500 hover:bg-red-50 rounded-md transition-colors font-medium"
            title="Delete campaign"
          >
            Delete
          </button>
        )}
        {confirming && (
          <div className="flex items-center gap-1">
            <button
              onClick={handleDelete}
              className="text-xs px-2 py-1 bg-red-500 text-white rounded-md hover:bg-red-600"
            >
              Confirm
            </button>
            <button
              onClick={handleCancelDelete}
              className="text-xs px-2 py-1 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </Link>
  );
}
