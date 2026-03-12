"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Campaign, Lead, OutreachMessage } from "@/lib/types";
import { campaignsApi, leadsApi, outreachApi } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

type SortKey = "score" | "first_name" | "company_name" | "title";
type SortDir = "asc" | "desc";

export default function ProspectsPage() {
  const params = useParams();
  const id = params.id as string;
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [minScore, setMinScore] = useState(0);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [leadMessages, setLeadMessages] = useState<OutreachMessage[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkAction, setBulkAction] = useState("");

  useEffect(() => {
    loadData();
  }, [id, statusFilter, minScore]);

  async function loadData() {
    setLoading(true);
    try {
      const [c, l] = await Promise.all([
        campaignsApi.get(id),
        leadsApi.list({
          campaign_id: id,
          status: statusFilter || undefined,
          min_score: minScore || undefined,
          limit: 200,
        }),
      ]);
      setCampaign(c);
      setLeads(l);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectLead(lead: Lead) {
    setSelectedLead(lead);
    try {
      const messages = await outreachApi.list({ lead_id: lead.id });
      setLeadMessages(messages);
    } catch {
      setLeadMessages([]);
    }
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function toggleSelect(leadId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(leadId)) {
        next.delete(leadId);
      } else {
        next.add(leadId);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectedIds.size === sorted.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(sorted.map((l) => l.id)));
    }
  }

  async function handleBulkAction() {
    if (!bulkAction || selectedIds.size === 0) return;
    try {
      await leadsApi.bulkUpdateStatus(Array.from(selectedIds), bulkAction);
      setSelectedIds(new Set());
      setBulkAction("");
      await loadData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Bulk action failed");
    }
  }

  const sorted = [...leads].sort((a, b) => {
    const aVal = a[sortKey] ?? "";
    const bVal = b[sortKey] ?? "";
    if (typeof aVal === "number" && typeof bVal === "number") {
      return sortDir === "asc" ? aVal - bVal : bVal - aVal;
    }
    return sortDir === "asc"
      ? String(aVal).localeCompare(String(bVal))
      : String(bVal).localeCompare(String(aVal));
  });

  if (loading && !campaign) return <p className="text-sm text-muted">Loading...</p>;

  return (
    <div className="flex gap-6">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-sm text-muted mb-4">
          <Link href="/" className="hover:text-foreground">Campaigns</Link>
          <span>/</span>
          <Link href={`/campaigns/${id}`} className="hover:text-foreground">{campaign?.name}</Link>
          <span>/</span>
          <span className="text-foreground">Prospects</span>
        </div>

        <h1 className="text-xl font-semibold text-foreground mb-4">
          Prospects ({leads.length})
        </h1>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-4">{error}</div>
        )}

        {/* Filters & Bulk Actions */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 border border-border rounded-lg text-sm"
          >
            <option value="">All Status</option>
            <option value="new">New</option>
            <option value="scored">Scored</option>
            <option value="enriched">Enriched</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
          </select>
          <input
            type="number"
            value={minScore || ""}
            onChange={(e) => setMinScore(Number(e.target.value) || 0)}
            placeholder="Min Score"
            className="w-28 px-3 py-1.5 border border-border rounded-lg text-sm"
          />
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-muted">{selectedIds.size} selected</span>
              <select
                value={bulkAction}
                onChange={(e) => setBulkAction(e.target.value)}
                className="px-3 py-1.5 border border-border rounded-lg text-sm"
              >
                <option value="">Bulk Action...</option>
                <option value="qualified">Mark Qualified</option>
                <option value="contacted">Mark Contacted</option>
                <option value="lost">Mark Lost</option>
              </select>
              <button
                onClick={handleBulkAction}
                disabled={!bulkAction}
                className="px-3 py-1.5 bg-primary text-white text-xs font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
              >
                Apply
              </button>
            </div>
          )}
        </div>

        {/* Table */}
        <div className="bg-white border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-gray-50">
                <th className="px-4 py-2.5 text-left w-8">
                  <input
                    type="checkbox"
                    checked={sorted.length > 0 && selectedIds.size === sorted.length}
                    onChange={toggleSelectAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <SortHeader label="Name" sortKey="first_name" current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Company" sortKey="company_name" current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Title" sortKey="title" current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Score" sortKey="score" current={sortKey} dir={sortDir} onSort={handleSort} />
                <th className="px-4 py-2.5 text-left font-medium text-muted">Email</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted">Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((lead) => (
                <tr
                  key={lead.id}
                  onClick={() => handleSelectLead(lead)}
                  className={`border-b border-border last:border-0 cursor-pointer hover:bg-gray-50 transition-colors ${
                    selectedLead?.id === lead.id ? "bg-blue-50" : ""
                  }`}
                >
                  <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(lead.id)}
                      onChange={() => toggleSelect(lead.id)}
                      className="rounded border-gray-300"
                    />
                  </td>
                  <td className="px-4 py-2.5 font-medium text-foreground">
                    {lead.first_name} {lead.last_name}
                  </td>
                  <td className="px-4 py-2.5 text-muted">{lead.company_name || "\u2014"}</td>
                  <td className="px-4 py-2.5 text-muted">{lead.title || "\u2014"}</td>
                  <td className="px-4 py-2.5">
                    <span className={`font-medium ${lead.score >= 70 ? "text-green-600" : lead.score >= 40 ? "text-amber-600" : "text-gray-400"}`}>
                      {lead.score}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {lead.email ? (
                      <span className="text-xs">
                        {lead.email_status === "verified" ? "verified" : lead.email_status === "guessed" ? "guessed" : "\u2014"}
                      </span>
                    ) : (
                      <span className="text-gray-300">{"\u2014"}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={lead.status} />
                  </td>
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted">
                    No prospects found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Panel */}
      {selectedLead && (
        <div className="w-80 shrink-0">
          <div className="bg-white border border-border rounded-lg p-5 sticky top-8">
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-medium text-foreground">
                {selectedLead.first_name} {selectedLead.last_name}
              </h3>
              <button
                onClick={() => setSelectedLead(null)}
                className="text-muted hover:text-foreground text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <p className="text-sm text-muted mb-1">{selectedLead.title} at {selectedLead.company_name}</p>
            {selectedLead.company_location && (
              <p className="text-xs text-muted mb-3">{selectedLead.company_location}</p>
            )}

            {selectedLead.email && (
              <p className="text-xs text-muted mb-1">{selectedLead.email}</p>
            )}
            {selectedLead.phone && (
              <p className="text-xs text-muted mb-1">{selectedLead.phone}</p>
            )}
            {selectedLead.linkedin_url && (
              <a href={selectedLead.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline">
                LinkedIn Profile
              </a>
            )}

            <div className="mt-4 pt-4 border-t border-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Score</span>
                <span className={`text-lg font-semibold ${selectedLead.score >= 70 ? "text-green-600" : selectedLead.score >= 40 ? "text-amber-600" : "text-gray-400"}`}>
                  {selectedLead.score}/100
                </span>
              </div>
              {selectedLead.score_reason && (
                <p className="text-xs text-muted italic">&ldquo;{selectedLead.score_reason}&rdquo;</p>
              )}
            </div>

            {leadMessages.length > 0 && (
              <div className="mt-4 pt-4 border-t border-border">
                <h4 className="text-sm font-medium mb-2">Outreach Drafts</h4>
                {leadMessages.map((msg) => (
                  <div key={msg.id} className="mb-2 p-2 bg-gray-50 rounded text-xs">
                    <p className="font-medium">{msg.channel}: {msg.subject || "(no subject)"}</p>
                    <p className="text-muted mt-1 line-clamp-3">{msg.body}</p>
                    <StatusBadge status={msg.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  current,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  const isActive = current === sortKey;
  return (
    <th
      className="px-4 py-2.5 text-left font-medium text-muted cursor-pointer hover:text-foreground select-none"
      onClick={() => onSort(sortKey)}
    >
      {label} {isActive && (dir === "asc" ? "\u2191" : "\u2193")}
    </th>
  );
}
