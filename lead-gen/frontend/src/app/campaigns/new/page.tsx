"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { ICPFilters } from "@/lib/types";
import { campaignsApi } from "@/lib/api";

export default function NewCampaignPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [icpText, setIcpText] = useState("");
  const [filters, setFilters] = useState<ICPFilters | null>(null);
  const [parsing, setParsing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleParseICP() {
    if (!icpText.trim()) return;
    setParsing(true);
    setError(null);
    try {
      const result = await campaignsApi.parseICP(icpText);
      setFilters(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to parse ICP");
    } finally {
      setParsing(false);
    }
  }

  async function handleCreate(autoRun: boolean) {
    if (!name.trim() || !icpText.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const campaign = await campaignsApi.createFromICP({
        name,
        icp_text: icpText,
        auto_run: autoRun,
      });
      router.push(`/campaigns/${campaign.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create campaign");
      setCreating(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground mb-6">Create Campaign</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-4">
          {error}
        </div>
      )}

      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Campaign Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Cybersecurity MSSPs Israel"
            className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Describe your ideal customer
          </label>
          <textarea
            value={icpText}
            onChange={(e) => setIcpText(e.target.value)}
            placeholder="Find cybersecurity MSSPs and resellers in Israel with 10-200 employees. Prefer founders, CEOs, channel managers, and sales directors."
            rows={4}
            className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-none"
          />
          <div className="flex justify-end mt-2">
            <button
              onClick={handleParseICP}
              disabled={parsing || !icpText.trim()}
              className="px-4 py-2 text-sm font-medium text-primary border border-primary rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {parsing ? "Parsing..." : "Parse ICP →"}
            </button>
          </div>
        </div>

        {filters && (
          <div className="bg-white border border-border rounded-lg p-5">
            <h3 className="text-sm font-medium text-foreground mb-4">Parsed Filters</h3>
            <div className="space-y-3">
              <FilterRow label="Titles" items={filters.person_titles} />
              <FilterRow label="Seniority" items={filters.person_seniorities} />
              <FilterRow label="Locations" items={filters.person_locations} />
              <FilterRow label="Industries" items={filters.organization_industries} />
              <FilterRow label="Keywords" items={filters.keywords} />
              {(filters.min_employees !== null || filters.max_employees !== null) && (
                <div>
                  <span className="text-xs text-muted">Employees:</span>
                  <span className="ml-2 text-sm text-foreground">
                    {filters.min_employees ?? "any"} - {filters.max_employees ?? "any"}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            onClick={() => handleCreate(false)}
            disabled={creating || !name.trim() || !icpText.trim()}
            className="px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Create Campaign
          </button>
          <button
            onClick={() => handleCreate(true)}
            disabled={creating || !name.trim() || !icpText.trim()}
            className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {creating ? "Creating..." : "Create & Run Pipeline"}
          </button>
        </div>
      </div>
    </div>
  );
}

function FilterRow({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <span className="text-xs text-muted">{label}:</span>
      <div className="flex flex-wrap gap-1.5 mt-1">
        {items.map((item) => (
          <span
            key={item}
            className="inline-flex items-center px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-md"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
