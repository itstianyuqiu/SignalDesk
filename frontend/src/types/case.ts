/**
 * Case workspace types — aligned with GET /api/v1/cases/:id (camelCase JSON).
 */

export type CaseStatus = "open" | "pending" | "resolved" | "closed";

export type CasePriority = "low" | "medium" | "high" | "critical";

export type CaseCategory =
  | "billing"
  | "technical"
  | "policy"
  | "incident"
  | "operations"
  | "general"
  | string;

export interface CaseDetailCore {
  id: string;
  caseKey: string;
  title: string;
  status: CaseStatus;
  priority: CasePriority;
  category: CaseCategory;
  categoryLabel: string;
  createdAt: string;
  updatedAt: string;
  /** Original Copilot session this case was created from, if any */
  createdFromSessionId?: string | null;
}

export type CaseSummarySource = "ai_draft" | "manual" | "placeholder";

export interface CaseSummaryBlock {
  text: string;
  source: CaseSummarySource;
  lastRefreshedAt?: string;
}

export type ActionItemStatus = "todo" | "in_progress" | "done";

export interface CaseActionItem {
  id: string;
  title: string;
  status: ActionItemStatus;
  owner?: string | null;
}

export interface RelatedSession {
  id: string;
  title: string;
  updatedAt: string;
  preview: string;
}

export interface RelatedDocument {
  id: string;
  title: string;
  tag: string;
  updatedAt: string;
}

export type TimelineEventKind =
  | "created"
  | "summary_updated"
  | "actions_generated"
  | "note"
  | "status_change"
  | "escalation"
  | string;

export interface CaseTimelineEvent {
  id: string;
  kind: TimelineEventKind;
  label: string;
  detail?: string;
  at: string;
  actor?: string;
}

export interface CasePageData {
  case: CaseDetailCore;
  summary: CaseSummaryBlock;
  actionItems: CaseActionItem[];
  relatedSessions: RelatedSession[];
  relatedDocuments: RelatedDocument[];
  timelineEvents: CaseTimelineEvent[];
}

export interface CaseListItem {
  id: string;
  caseKey: string;
  title: string;
  status: CaseStatus;
  priority: CasePriority;
  categoryLabel: string;
  updatedAt: string;
}

/** Raw API shape (camelCase) */
export interface CaseDetailApi {
  id: string;
  caseKey: string;
  title: string;
  summary: string;
  status: string;
  priority: string;
  category: string | null;
  createdFromSessionId: string | null;
  createdAt: string;
  updatedAt: string;
  actionItems: Array<{
    id: string;
    title: string;
    status: string;
    owner: string | null;
  }>;
  relatedSessions: Array<{
    id: string;
    title: string | null;
    updatedAt: string;
    preview: string;
  }>;
  relatedDocuments: Array<{
    id: string;
    title: string;
    tag: string;
    updatedAt: string;
  }>;
  timelineEvents: Array<{
    id: string;
    kind: string;
    label: string;
    detail?: string | null;
    at: string;
    actor?: string | null;
  }>;
}
