import type {
  ActionItemStatus,
  CaseDetailApi,
  CasePageData,
  CasePriority,
  CaseStatus,
} from "@/types/case";

const STATUSES: CaseStatus[] = ["open", "pending", "resolved", "closed"];
const PRIORITIES: CasePriority[] = ["low", "medium", "high", "critical"];

function asStatus(s: string): CaseStatus {
  return STATUSES.includes(s as CaseStatus) ? (s as CaseStatus) : "open";
}

function asPriority(p: string): CasePriority {
  return PRIORITIES.includes(p as CasePriority) ? (p as CasePriority) : "medium";
}

function asActionStatus(s: string): ActionItemStatus {
  return s === "todo" || s === "in_progress" || s === "done" ? s : "todo";
}

export function mapCaseDetailApiToPageData(api: CaseDetailApi): CasePageData {
  const cat = api.category?.trim() || "General";
  return {
    case: {
      id: api.id,
      caseKey: api.caseKey,
      title: api.title,
      status: asStatus(api.status),
      priority: asPriority(api.priority),
      category: cat,
      categoryLabel: cat,
      createdAt: api.createdAt,
      updatedAt: api.updatedAt,
      createdFromSessionId: api.createdFromSessionId,
    },
    summary: {
      text: api.summary || "No summary yet.",
      source: "manual",
    },
    actionItems: api.actionItems.map((a) => ({
      id: a.id,
      title: a.title,
      status: asActionStatus(a.status),
      owner: a.owner,
    })),
    relatedSessions: api.relatedSessions.map((s) => ({
      id: s.id,
      title: s.title?.trim() || "Copilot session",
      updatedAt: s.updatedAt,
      preview: s.preview,
    })),
    relatedDocuments: api.relatedDocuments.map((d) => ({
      id: d.id,
      title: d.title,
      tag: d.tag,
      updatedAt: d.updatedAt,
    })),
    timelineEvents: api.timelineEvents.map((e) => ({
      id: e.id,
      kind: e.kind,
      label: e.label,
      detail: e.detail ?? undefined,
      at: e.at,
      actor: e.actor ?? undefined,
    })),
  };
}
