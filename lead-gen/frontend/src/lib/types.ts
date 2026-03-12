export interface Campaign {
  id: string;
  name: string;
  description: string | null;
  icp_raw_text: string | null;
  parsed_filters: string | null;
  target_titles: string | null;
  target_industries: string | null;
  target_seniority: string | null;
  target_locations: string | null;
  min_employees: number | null;
  max_employees: number | null;
  keywords: string | null;
  status: string;
  pipeline_stage: string;
  total_leads: number;
  enriched_leads: number;
  contacted_leads: number;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  email_status: string | null;
  phone: string | null;
  linkedin_url: string | null;
  title: string | null;
  seniority: string | null;
  department: string | null;
  company_name: string | null;
  company_domain: string | null;
  company_industry: string | null;
  company_size: number | null;
  company_location: string | null;
  source: string;
  status: string;
  score: number;
  score_reason: string | null;
  campaign_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface OutreachMessage {
  id: string;
  lead_id: string;
  channel: string;
  sequence_step: number;
  subject: string | null;
  body: string;
  status: string;
  sent_at: string | null;
  created_at: string;
}

export interface ICPFilters {
  person_titles: string[];
  person_seniorities: string[];
  person_locations: string[];
  organization_industries: string[];
  organization_locations: string[];
  min_employees: number | null;
  max_employees: number | null;
  keywords: string[];
}

export interface PipelineStatus {
  campaign_id: string;
  pipeline_stage: string;
  total_leads: number;
  scored_leads: number;
  enriched_leads: number;
  drafts_generated: number;
}

export interface PipelineStats {
  total_leads: number;
  new: number;
  enriched: number;
  scored: number;
  contacted: number;
  qualified: number;
  converted: number;
  lost: number;
  total_deals_value: number;
  avg_score: number;
}
