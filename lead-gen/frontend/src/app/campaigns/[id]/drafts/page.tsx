"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Campaign, Lead, OutreachMessage } from "@/lib/types";
import { campaignsApi, leadsApi, outreachApi } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

interface DraftWithLead {
  message: OutreachMessage;
  lead: Lead | null;
}

export default function DraftsPage() {
  const params = useParams();
  const id = params.id as string;
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [drafts, setDrafts] = useState<DraftWithLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, [id]);

  async function loadData() {
    try {
      const [c, leads, messages] = await Promise.all([
        campaignsApi.get(id),
        leadsApi.list({ campaign_id: id, limit: 200 }),
        outreachApi.list({ campaign_id: id }),
      ]);
      setCampaign(c);

      const leadsMap = new Map(leads.map((l) => [l.id, l]));
      setDrafts(
        messages.map((m) => ({
          message: m,
          lead: leadsMap.get(m.lead_id) || null,
        })),
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  function handleStartEdit(message: OutreachMessage) {
    setEditingId(message.id);
    setEditSubject(message.subject || "");
    setEditBody(message.body);
  }

  function handleCancelEdit() {
    setEditingId(null);
    setEditSubject("");
    setEditBody("");
  }

  async function handleSaveEdit(messageId: string) {
    setSaving(true);
    try {
      const updated = await outreachApi.update(messageId, {
        subject: editSubject || undefined,
        body: editBody,
      });
      setDrafts((prev) =>
        prev.map((d) =>
          d.message.id === messageId ? { ...d, message: updated } : d,
        ),
      );
      setEditingId(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove(messageId: string) {
    try {
      await outreachApi.send([messageId]);
      setDrafts((prev) =>
        prev.map((d) =>
          d.message.id === messageId
            ? { ...d, message: { ...d.message, status: "sent" } }
            : d,
        ),
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to approve");
    }
  }

  async function handleBulkApprove() {
    const draftIds = drafts
      .filter((d) => d.message.status === "draft")
      .map((d) => d.message.id);
    if (draftIds.length === 0) return;

    try {
      await outreachApi.send(draftIds);
      setDrafts((prev) =>
        prev.map((d) =>
          draftIds.includes(d.message.id)
            ? { ...d, message: { ...d.message, status: "sent" } }
            : d,
        ),
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to bulk approve");
    }
  }

  if (loading) return <p className="text-sm text-muted">Loading...</p>;

  const draftCount = drafts.filter((d) => d.message.status === "draft").length;

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-2 text-sm text-muted mb-4">
        <Link href="/" className="hover:text-foreground">Campaigns</Link>
        <span>/</span>
        <Link href={`/campaigns/${id}`} className="hover:text-foreground">{campaign?.name}</Link>
        <span>/</span>
        <span className="text-foreground">Drafts</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-foreground">
          Drafts ({drafts.length})
        </h1>
        {draftCount > 0 && (
          <button
            onClick={handleBulkApprove}
            className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-blue-600 transition-colors"
          >
            Approve All ({draftCount})
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-4">{error}</div>
      )}

      {drafts.length === 0 && (
        <p className="text-sm text-muted py-8 text-center">No drafts generated yet.</p>
      )}

      <div className="space-y-4">
        {drafts.map(({ message, lead }) => (
          <div key={message.id} className="bg-white border border-border rounded-lg p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="text-sm font-medium text-foreground">
                  To: {lead ? `${lead.first_name} ${lead.last_name}` : "Unknown"}
                  {lead?.title && ` (${lead.title}`}
                  {lead?.company_name && `, ${lead.company_name})`}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-muted capitalize">{message.channel}</span>
                  {lead && (
                    <span className="text-xs text-muted">Score: {lead.score}</span>
                  )}
                </div>
              </div>
              <StatusBadge status={message.status} />
            </div>

            {editingId === message.id ? (
              <>
                {message.channel === "email" && (
                  <div className="mb-3">
                    <label className="block text-xs text-muted mb-1">Subject</label>
                    <input
                      type="text"
                      value={editSubject}
                      onChange={(e) => setEditSubject(e.target.value)}
                      className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    />
                  </div>
                )}
                <div className="mb-3">
                  <label className="block text-xs text-muted mb-1">Body</label>
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    rows={6}
                    className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-none"
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={handleCancelEdit}
                    className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleSaveEdit(message.id)}
                    disabled={saving || !editBody.trim()}
                    className="px-3 py-1.5 bg-primary text-white text-xs font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                </div>
              </>
            ) : (
              <>
                {message.subject && (
                  <div className="mb-3">
                    <label className="block text-xs text-muted mb-1">Subject</label>
                    <p className="text-sm text-foreground bg-gray-50 px-3 py-2 rounded border border-border">
                      {message.subject}
                    </p>
                  </div>
                )}

                <div className="mb-3">
                  <label className="block text-xs text-muted mb-1">Body</label>
                  <p className="text-sm text-foreground bg-gray-50 px-3 py-2 rounded border border-border whitespace-pre-wrap">
                    {message.body}
                  </p>
                </div>

                {message.status === "draft" && (
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => handleStartEdit(message)}
                      className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleApprove(message.id)}
                      className="px-3 py-1.5 bg-green-500 text-white text-xs font-medium rounded-lg hover:bg-green-600 transition-colors"
                    >
                      Approve
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
