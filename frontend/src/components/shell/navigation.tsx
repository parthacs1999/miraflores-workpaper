"use client";
import {
  createContext,
  useContext,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  Activity,
  ArrowLeftRight,
  BookOpen,
  BriefcaseBusiness,
  CalendarClock,
  CheckCheck,
  ClipboardCheck,
  FileCheck2,
  FileClock,
  FileDiff,
  FileSearch,
  Files,
  FileSignature,
  GitBranch,
  GitCompareArrows,
  History,
  LayoutDashboard,
  LockKeyhole,
  MessageSquare,
  NotebookPen,
  ReceiptText,
  Scale,
  Send,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
export const navigationGroups: {
  label: string;
  items: { id: string; label: string; icon: LucideIcon; admin?: boolean }[];
}[] = [
  {
    label: "Overview",
    items: [
      {
        id: "dashboard",
        label: "Dashboard",
        icon: LayoutDashboard,
        admin: true,
      },
      {
        id: "readiness",
        label: "Filing Readiness",
        icon: ShieldCheck,
        admin: true,
      },
      { id: "tasks", label: "Tasks", icon: CalendarClock, admin: true },
    ],
  },
  {
    label: "Tax Workpaper",
    items: [
      { id: "return", label: "Return Explorer", icon: BookOpen },
      { id: "documents", label: "Evidence & Documents", icon: Files },
      { id: "reconciliation", label: "Reconciliation & Findings", icon: Scale },
      { id: "adjustments", label: "Adjustments", icon: SlidersHorizontal },
    ],
  },
  {
    label: "Review & Collaboration",
    items: [
      { id: "diligence", label: "Diligence", icon: ClipboardCheck },
      { id: "notes", label: "Review Notes", icon: NotebookPen },
      { id: "signoffs", label: "Sign-offs", icon: CheckCheck },
      { id: "collaboration", label: "Collaboration", icon: MessageSquare },
      { id: "attachments", label: "Supporting Attachments", icon: FileSearch },
      { id: "bulk", label: "Bulk Actions & Undo", icon: Settings2 },
    ],
  },
  {
    label: "Analysis",
    items: [
      { id: "version", label: "Version Comparison", icon: GitCompareArrows },
      { id: "whatif", label: "What-if Scenarios", icon: Sparkles },
      { id: "replay", label: "Timeline Replay", icon: History },
      { id: "impact", label: "Change Impact", icon: GitBranch },
    ],
  },
  {
    label: "Filing",
    items: [
      { id: "finalization", label: "Finalization", icon: FileCheck2 },
      { id: "filing", label: "Filing Status", icon: Send },
      { id: "extensions", label: "Extensions & Payments", icon: Wallet },
      {
        id: "authorization",
        label: "Client Authorization",
        icon: FileSignature,
      },
      { id: "amendments", label: "Amendments", icon: FileDiff },
      { id: "notices", label: "Notices & Examination", icon: FileClock },
      {
        id: "carryovers",
        label: "Carryovers & Planning",
        icon: ArrowLeftRight,
      },
    ],
  },
  {
    label: "Firm",
    items: [
      { id: "assignments", label: "Assignments", icon: Users, admin: true },
      {
        id: "operations",
        label: "Firm Operations",
        icon: BriefcaseBusiness,
        admin: true,
      },
      {
        id: "security",
        label: "Security & Access",
        icon: LockKeyhole,
        admin: true,
      },
    ],
  },
];
export const extraViews = [
  { id: "accountability", label: "Document Accountability", icon: FileCheck2 },
  { id: "resolver", label: "Evidence Resolver", icon: ReceiptText },
  { id: "findings", label: "Review Findings", icon: Activity },
];
export function viewInfo(view: string) {
  const group = navigationGroups.find((g) =>
    g.items.some((i) => i.id === view),
  );
  const item =
    group?.items.find((i) => i.id === view) ??
    extraViews.find((i) => i.id === view);
  return {
    label: item?.label ?? "Dashboard",
    group: group?.label ?? "Tax Workpaper",
  };
}
export const filingViews: Record<string, string> = {
  finalization: "Finalization",
  filing: "Filing Status",
  extensions: "Extensions & Payments",
  authorization: "Client Authorization",
  amendments: "Amendments",
  notices: "Notices & Examination",
  carryovers: "Carryovers & Planning",
};
export const analysisViews: Record<string, string> = {
  version: "Version Comparison",
  whatif: "What-if Analysis",
  replay: "Timeline Replay",
  impact: "Change Impact",
};
export const workpaperViews = [
  "return",
  "documents",
  "accountability",
  "resolver",
  "findings",
  "reconciliation",
  "adjustments",
];
export type Navigation = {
  view: string;
  navigate: (view: string, reference?: string) => void;
  reference: string | null;
  setView: Dispatch<SetStateAction<string>>;
  legacy?: boolean;
};
export const NavigationContext = createContext<Navigation | null>(null);
export const useAppNavigation = () => useContext(NavigationContext);

/** Workflow APIs already filter these views to the active engagement assignment. */
export const scopedViews = [
  "dashboard",
  "readiness",
  "tasks",
  "assignments",
  "diligence",
  "notes",
  "signoffs",
  "collaboration",
  "attachments",
  "bulk",
  "operations",
  "security",
];
